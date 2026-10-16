"""Download one month of Seoul metropolitan living-mobility files.

The script discovers the current file identifiers from the official Seoul Open
Data pages instead of guessing download URLs.  It is a dry run unless the
``--download`` flag is supplied.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PAGE_URL = "https://data.seoul.go.kr/dataList/{dataset_id}/F/1/datasetView.do?tab=F"
DOWNLOAD_URL = (
    "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
)
USER_AGENT = "early-morning-mobility-data-prep/1.0"
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class Dataset:
    dataset_id: str
    filename_pattern: re.Pattern[str]
    output_dir: Path


@dataclass(frozen=True)
class RemoteFile:
    dataset_id: str
    filename: str
    sequence: str
    source_page: str
    output_dir: Path


DATASETS = (
    Dataset(
        dataset_id="OA-22300",
        filename_pattern=re.compile(
            r"^seoul_purpose_admdong3_(?P<date>\d{8})\.zip$", re.IGNORECASE
        ),
        output_dir=Path("data/raw/mobility/OA-22300"),
    ),
    Dataset(
        dataset_id="OA-22657",
        filename_pattern=re.compile(
            r"^seoul_trans_admdong3_final_(?P<date>\d{8})\.zip$", re.IGNORECASE
        ),
        output_dir=Path("data/raw/mobility/OA-22657"),
    ),
)


FILE_LINK_PATTERN = re.compile(
    r'title="(?P<filename>[^"<>]+\.zip)"[^>]*?'
    r'onclick="javascript:downloadFile\(\'(?P<sequence>[^\']+)\'\);"',
    re.IGNORECASE,
)


def build_opener() -> urllib.request.OpenerDirector:
    cookie_jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))


def request_with_retries(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    retries: int,
):
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return opener.open(request, timeout=120)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt == retries:
                break
            delay = min(30, 2 ** (attempt - 1))
            print(
                f"  요청 실패 ({attempt}/{retries}): {exc}; {delay}초 후 재시도",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise RuntimeError(f"요청이 {retries}회 모두 실패했습니다: {last_error}")


def fetch_page(
    opener: urllib.request.OpenerDirector, dataset: Dataset, retries: int
) -> tuple[str, str]:
    url = PAGE_URL.format(dataset_id=dataset.dataset_id)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
    )
    with request_with_retries(opener, request, retries) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return url, response.read().decode(charset, errors="replace")


def discover_files(
    opener: urllib.request.OpenerDirector,
    dataset: Dataset,
    month: str,
    retries: int,
) -> list[RemoteFile]:
    source_page, html = fetch_page(opener, dataset, retries)
    month_compact = month.replace("-", "")
    discovered: dict[str, RemoteFile] = {}

    for match in FILE_LINK_PATTERN.finditer(html):
        filename = match.group("filename")
        filename_match = dataset.filename_pattern.match(filename)
        if not filename_match:
            continue
        if not filename_match.group("date").startswith(month_compact):
            continue
        discovered[filename] = RemoteFile(
            dataset_id=dataset.dataset_id,
            filename=filename,
            sequence=match.group("sequence"),
            source_page=source_page,
            output_dir=dataset.output_dir,
        )

    return sorted(discovered.values(), key=lambda item: item.filename)


def is_valid_zip(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile):
        return False


def make_download_request(remote_file: RemoteFile, offset: int = 0):
    payload = urllib.parse.urlencode(
        {
            "infId": remote_file.dataset_id,
            "seqNo": "",
            "seq": remote_file.sequence,
            "infSeq": "1",
        }
    ).encode("ascii")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "identity",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": remote_file.source_page,
    }
    if offset:
        headers["Range"] = f"bytes={offset}-"
    return urllib.request.Request(
        DOWNLOAD_URL, data=payload, headers=headers, method="POST"
    )


def stream_download(
    opener: urllib.request.OpenerDirector,
    remote_file: RemoteFile,
    retries: int,
    overwrite: bool,
) -> dict[str, object]:
    remote_file.output_dir.mkdir(parents=True, exist_ok=True)
    destination = remote_file.output_dir / remote_file.filename
    partial = destination.with_name(destination.name + ".part")

    if destination.exists() and not overwrite:
        if is_valid_zip(destination):
            print(f"  건너뜀(정상 파일 존재): {destination}")
            return {
                "dataset_id": remote_file.dataset_id,
                "filename": remote_file.filename,
                "status": "skipped_existing",
                "bytes": destination.stat().st_size,
            }
        raise RuntimeError(
            f"기존 파일이 ZIP 검사를 통과하지 못했습니다: {destination}\n"
            "확인 후 제거하거나 --overwrite를 사용하세요."
        )

    if overwrite:
        partial.unlink(missing_ok=True)

    offset = partial.stat().st_size if partial.exists() else 0
    request = make_download_request(remote_file, offset)
    response = request_with_retries(opener, request, retries)

    if offset and getattr(response, "status", None) != 206:
        response.close()
        print("  서버가 이어받기를 지원하지 않아 처음부터 다시 받습니다.")
        partial.unlink(missing_ok=True)
        offset = 0
        response = request_with_retries(
            opener, make_download_request(remote_file), retries
        )

    mode = "ab" if offset else "wb"
    content_length = response.headers.get("Content-Length")
    expected_total = (
        offset + int(content_length) if content_length and content_length.isdigit() else None
    )
    downloaded = offset
    last_report = time.monotonic()

    with response, partial.open(mode) as output:
        while True:
            chunk = response.read(CHUNK_SIZE)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            now = time.monotonic()
            if now - last_report >= 5:
                if expected_total:
                    percent = downloaded / expected_total * 100
                    print(
                        f"  {remote_file.filename}: "
                        f"{downloaded / 1024**2:,.1f} MiB ({percent:.1f}%)"
                    )
                else:
                    print(
                        f"  {remote_file.filename}: {downloaded / 1024**2:,.1f} MiB"
                    )
                last_report = now

    if expected_total is not None and downloaded != expected_total:
        raise RuntimeError(
            f"다운로드 크기가 예상과 다릅니다: {remote_file.filename} "
            f"({downloaded} != {expected_total})"
        )
    if not is_valid_zip(partial):
        raise RuntimeError(
            f"다운로드 파일이 정상 ZIP이 아닙니다: {partial}. "
            "파일은 .part 상태로 보존했습니다."
        )

    os.replace(partial, destination)
    print(f"  완료: {destination} ({destination.stat().st_size / 1024**2:,.1f} MiB)")
    return {
        "dataset_id": remote_file.dataset_id,
        "filename": remote_file.filename,
        "status": "downloaded",
        "bytes": destination.stat().st_size,
    }


def write_manifest(month: str, records: list[dict[str, object]]) -> Path:
    manifest_path = Path("data/raw/mobility") / f"download_manifest_{month}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "month": month,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "download_url": DOWNLOAD_URL,
        "records": records,
    }
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, manifest_path)
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "서울 열린데이터광장에서 OA-22300·OA-22657의 지정 월 파일을 "
            "찾아 일괄 다운로드합니다. 기본값은 목록 확인만 수행합니다."
        )
    )
    parser.add_argument(
        "--month",
        default="2026-09",
        help="대상 월(YYYY-MM). 기본값: 2026-09",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="실제 다운로드 실행. 생략하면 목록만 표시합니다.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 최종 파일을 다시 다운로드합니다.",
    )
    parser.add_argument(
        "--retries", type=int, default=4, help="요청별 최대 재시도 횟수. 기본값: 4"
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", args.month):
        raise SystemExit("--month는 YYYY-MM 형식이어야 합니다. 예: 2026-09")
    if args.retries < 1:
        raise SystemExit("--retries는 1 이상이어야 합니다.")


def main() -> int:
    args = parse_args()
    validate_args(args)
    opener = build_opener()
    planned: list[RemoteFile] = []

    print(f"대상 월: {args.month}")
    for dataset in DATASETS:
        files = discover_files(opener, dataset, args.month, args.retries)
        print(f"\n{dataset.dataset_id}: {len(files)}개 파일")
        for item in files:
            print(f"  {item.filename}")
        planned.extend(files)

    if not planned:
        print("대상 파일을 찾지 못했습니다.", file=sys.stderr)
        return 2

    counts = {dataset.dataset_id: 0 for dataset in DATASETS}
    for item in planned:
        counts[item.dataset_id] += 1
    incomplete = [dataset_id for dataset_id, count in counts.items() if count < 28]
    if incomplete:
        print(
            "\n경고: 다음 데이터셋은 한 달치로 보기 어려운 개수입니다: "
            + ", ".join(f"{dataset_id}={counts[dataset_id]}개" for dataset_id in incomplete),
            file=sys.stderr,
        )

    if not args.download:
        print(
            f"\n목록 확인 완료: 총 {len(planned)}개. "
            "실제 다운로드하려면 --download를 추가하세요."
        )
        return 0

    print(f"\n총 {len(planned)}개 파일 다운로드를 시작합니다.")
    records: list[dict[str, object]] = []
    for index, item in enumerate(planned, start=1):
        print(f"\n[{index}/{len(planned)}] {item.dataset_id} / {item.filename}")
        record = stream_download(opener, item, args.retries, args.overwrite)
        records.append(record)
        write_manifest(args.month, records)

    manifest_path = write_manifest(args.month, records)
    print(f"\n완료. 기록: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
