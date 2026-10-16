#!/usr/bin/env python3
"""Acquire raw Seoul Metro timetable API responses for a reference date."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTIONS = ["상행", "하행", "내선", "외선"]
DEFAULT_DAY_TYPES = ["평일", "주말", "공휴일", "상시"]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def build_url(endpoint: str, api_key: str, params: dict[str, str | int]) -> str:
    key_part = urllib.parse.quote(api_key, safe="%")
    query = urllib.parse.urlencode(params)
    return f"{endpoint}?serviceKey={key_part}&{query}"


def fetch_json(url: str, retries: int, timeout: int) -> tuple[bytes, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "dawn-mobility-data-acquisition/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
            return body, json.loads(body.decode("utf-8-sig"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"API request failed after {retries} attempts: {exc}") from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def normalize_items(payload: dict[str, Any]) -> tuple[str, str, int, list[dict[str, Any]]]:
    response = payload.get("response", payload)
    header = response.get("header", {}) if isinstance(response, dict) else {}
    body = response.get("body", {}) if isinstance(response, dict) else {}
    code = str(header.get("resultCode", ""))
    message = str(header.get("resultMsg", ""))
    total = int(body.get("totalCount", 0) or 0) if isinstance(body, dict) else 0
    items_container = body.get("items", {}) if isinstance(body, dict) else {}
    items = items_container.get("item", []) if isinstance(items_container, dict) else []
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        items = []
    return code, message, total, items


def atomic_write(path: Path, content: bytes) -> None:
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_bytes(content)
    temp.replace(path)


def safe_name(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search-date", default="2026-09-15T04:30:00")
    parser.add_argument("--line-query", default="호선", help="lineNm contains-search value")
    parser.add_argument("--directions", nargs="+", default=DEFAULT_DIRECTIONS)
    parser.add_argument("--day-types", nargs="+", default=DEFAULT_DAY_TYPES)
    parser.add_argument("--temporary", choices=["Y", "N"], default="N")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--snapshot-date", default=datetime.now().astimezone().strftime("%Y%m%d"))
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    base_url = env.get("SEOUL_METRO_TIMETABLE_API_URL", "").rstrip("/")
    api_key = env.get("SEOUL_METRO_TIMETABLE_API_KEY", "")
    if not base_url or not api_key:
        print("Missing SEOUL_METRO_TIMETABLE_API_URL or SEOUL_METRO_TIMETABLE_API_KEY in .env", file=sys.stderr)
        return 2
    endpoint = base_url if base_url.endswith("/getTrainSch") else base_url + "/getTrainSch"

    output_dir = ROOT / "data" / "raw" / "subway" / "data-go-15143847" / f"snapshot_{args.snapshot_date}"
    output_dir.mkdir(parents=True, exist_ok=True)
    requests_manifest: list[dict[str, Any]] = []
    total_saved = 0

    for day_type in args.day_types:
        for direction in args.directions:
            base_params: dict[str, str | int] = {
                "pageNo": 1,
                "numOfRows": args.page_size,
                "dataType": "JSON",
                "tmprTmtblYn": args.temporary,
                "upbdnbSe": direction,
                "wkndSe": day_type,
                "lineNm": args.line_query,
                "searchDt": args.search_date,
            }
            first_filename = f"wknd_{safe_name(day_type)}__dir_{safe_name(direction)}__page_0001.json"
            first_destination = output_dir / first_filename
            if first_destination.exists():
                first_body = first_destination.read_bytes()
                first_payload = json.loads(first_body.decode("utf-8-sig"))
                print(f"resuming {day_type}/{direction} from saved page 1 ...", flush=True)
            else:
                first_url = build_url(endpoint, api_key, base_params)
                print(f"requesting {day_type}/{direction} ...", flush=True)
                first_body, first_payload = fetch_json(first_url, args.retries, args.timeout)
            code, message, total, first_items = normalize_items(first_payload)
            if code not in ("0", "00", "03"):
                raise RuntimeError(f"{day_type}/{direction}: API error {code}: {message}")
            pages = max(1, math.ceil(total / args.page_size))
            print(f"{day_type}/{direction}: total={total}, pages={pages}, code={code}", flush=True)

            for page_no in range(1, pages + 1):
                params = dict(base_params)
                params["pageNo"] = page_no
                filename = f"wknd_{safe_name(day_type)}__dir_{safe_name(direction)}__page_{page_no:04d}.json"
                destination = output_dir / filename
                if destination.exists():
                    body = destination.read_bytes()
                    payload = json.loads(body.decode("utf-8-sig"))
                    page_code, page_message, _, items = normalize_items(payload)
                    if page_code not in ("0", "00", "03"):
                        raise RuntimeError(f"saved {day_type}/{direction}/page {page_no}: {page_code}: {page_message}")
                elif page_no == 1:
                    body, payload, items = first_body, first_payload, first_items
                else:
                    url = build_url(endpoint, api_key, params)
                    body, payload = fetch_json(url, args.retries, args.timeout)
                    page_code, page_message, _, items = normalize_items(payload)
                    if page_code not in ("0", "00", "03"):
                        raise RuntimeError(f"{day_type}/{direction}/page {page_no}: {page_code}: {page_message}")

                if not destination.exists():
                    atomic_write(destination, body)
                total_saved += len(items)
                requests_manifest.append(
                    {
                        "file": filename,
                        "wkndSe": day_type,
                        "upbdnbSe": direction,
                        "pageNo": page_no,
                        "row_count": len(items),
                        "reported_total_count": total,
                        "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "result_code": code,
                        "result_message": message,
                    }
                )
                time.sleep(max(args.delay, 0))

    manifest = {
        "dataset_id": "data-go-15143847",
        "endpoint_without_key": endpoint,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_date": args.snapshot_date,
        "search_date": args.search_date,
        "line_query": args.line_query,
        "temporary_timetable": args.temporary,
        "directions": args.directions,
        "day_types": args.day_types,
        "format": "raw JSON API responses",
        "saved_row_count_across_queries": total_saved,
        "requests": requests_manifest,
    }
    atomic_write(output_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
