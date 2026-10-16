#!/usr/bin/env python3
"""Download Seoul Open Data master datasets as immutable raw JSON pages.

The API key is read from the repository's .env file and is never written to
responses or manifests. This script only acquires raw data; it does not clean
or analyse it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "OA-21230": ("bus", "SEOUL_OA_21230_SERVICE"),
    "OA-21231": ("bus", "SEOUL_OA_21231_SERVICE"),
    "OA-21232": ("subway", "SEOUL_OA_21232_SERVICE"),
    "OA-21233": ("bus", "SEOUL_OA_21233_SERVICE"),
}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if v})
    return values


def fetch_json(url: str, retries: int = 4) -> tuple[bytes, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "dawn-mobility-data-acquisition/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read()
            return body, json.loads(body.decode("utf-8-sig"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(f"API request failed after {retries} attempts: {exc}") from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def response_block(payload: dict[str, Any], service: str) -> dict[str, Any]:
    block = payload.get(service)
    if isinstance(block, dict):
        return block
    for value in payload.values():
        if isinstance(value, dict) and "list_total_count" in value:
            return value
    error = payload.get("RESULT")
    if isinstance(error, dict):
        raise RuntimeError(f"Seoul API error {error.get('CODE')}: {error.get('MESSAGE')}")
    raise RuntimeError(f"Unexpected response structure; service block {service!r} not found")


def atomic_write(path: Path, content: bytes) -> None:
    temp = path.with_suffix(path.suffix + ".part")
    temp.write_bytes(content)
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--datasets", nargs="+", choices=sorted(DATASETS), default=sorted(DATASETS))
    parser.add_argument("--page-size", type=int, default=1000, choices=range(1, 1001), metavar="1..1000")
    parser.add_argument("--snapshot-date", default=datetime.now().astimezone().strftime("%Y%m%d"))
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    base_url = env.get("SEOUL_OPEN_DATA_API_BASE_URL", "").rstrip("/")
    api_key = env.get("SEOUL_OPEN_DATA_API_KEY", "")
    if not base_url or not api_key:
        print("Missing SEOUL_OPEN_DATA_API_BASE_URL or SEOUL_OPEN_DATA_API_KEY in .env", file=sys.stderr)
        return 2

    for dataset_id in args.datasets:
        category, service_var = DATASETS[dataset_id]
        service = env.get(service_var, "")
        if not service:
            raise RuntimeError(f"Missing {service_var} in .env")

        output_dir = ROOT / "data" / "raw" / category / dataset_id / f"snapshot_{args.snapshot_date}"
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.json"

        first_url = f"{base_url}/{api_key}/json/{service}/1/1/"
        _, first_payload = fetch_json(first_url)
        first_block = response_block(first_payload, service)
        total = int(first_block.get("list_total_count", 0))
        print(f"{dataset_id}: service={service}, total={total}")

        pages: list[dict[str, Any]] = []
        collected = 0
        for start in range(1, total + 1, args.page_size):
            end = min(start + args.page_size - 1, total)
            filename = f"page_{start:06d}_{end:06d}.json"
            destination = output_dir / filename
            url = f"{base_url}/{api_key}/json/{service}/{start}/{end}/"
            body, payload = fetch_json(url)
            block = response_block(payload, service)
            result = block.get("RESULT", {})
            if isinstance(result, dict) and result.get("CODE") not in (None, "INFO-000"):
                raise RuntimeError(f"{dataset_id} {start}-{end}: {result}")
            rows = block.get("row", [])
            if not isinstance(rows, list):
                raise RuntimeError(f"{dataset_id} {start}-{end}: row is not a list")
            atomic_write(destination, body)
            digest = hashlib.sha256(body).hexdigest()
            pages.append(
                {
                    "file": filename,
                    "start_index": start,
                    "end_index": end,
                    "row_count": len(rows),
                    "bytes": len(body),
                    "sha256": digest,
                    "source_url_without_key": f"{base_url}/REDACTED/json/{service}/{start}/{end}/",
                }
            )
            collected += len(rows)
            print(f"  saved {filename}: {len(rows)} rows")
            time.sleep(max(args.delay, 0))

        manifest = {
            "dataset_id": dataset_id,
            "service": service,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_date": args.snapshot_date,
            "format": "raw Seoul Open Data JSON response pages",
            "list_total_count": total,
            "collected_row_count": collected,
            "pages": pages,
        }
        atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        if collected != total:
            raise RuntimeError(f"{dataset_id}: expected {total} rows but collected {collected}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
