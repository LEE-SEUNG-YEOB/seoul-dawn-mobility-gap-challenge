#!/usr/bin/env python3
"""Acquire OA-15334 first/last bus time responses, resumably.

Each API call addresses one (ARS stop number, route ID) pair. Raw XML is kept
inside JSONL records together with non-secret request metadata. Existing
records are detected on restart, so the script can be run over multiple days.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]


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


def iter_rows(directory: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(directory.glob("page_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        for value in payload.values():
            if isinstance(value, dict) and isinstance(value.get("row"), list):
                yield from value["row"]
                break


def build_pairs(snapshot_date: str) -> list[tuple[str, str, str]]:
    station_dir = ROOT / "data" / "raw" / "bus" / "OA-21231" / f"snapshot_{snapshot_date}"
    node_dir = ROOT / "data" / "raw" / "bus" / "OA-21233" / f"snapshot_{snapshot_date}"
    if not station_dir.exists() or not node_dir.exists():
        raise RuntimeError("OA-21231 and OA-21233 snapshots must be downloaded first")
    stations = {
        str(row.get("CRTR_ID")): str(row.get("CRTR_NO"))
        for row in iter_rows(station_dir)
        if row.get("CRTR_ID") not in (None, "")
        and row.get("CRTR_NO") not in (None, "", "0")
        and len(str(row.get("CRTR_NO"))) == 5
    }
    unique: dict[tuple[str, str], str] = {}
    for row in iter_rows(node_dir):
        station_id = str(row.get("CRTR_ID", ""))
        route_id = str(row.get("RTE_ID", ""))
        ars_id = stations.get(station_id, "")
        if ars_id and route_id:
            unique[(ars_id, route_id)] = station_id
    return [(ars_id, route_id, unique[(ars_id, route_id)]) for ars_id, route_id in sorted(unique)]


def completed_pairs(output_dir: Path) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    for path in sorted(output_dir.glob("responses_*.jsonl")):
        with path.open("r", encoding="utf-8") as stream:
            for line_no, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(f"Invalid JSONL in {path.name}, line {line_no}") from exc
                if str(record.get("status_code", "")) not in ("", "REQUEST_ERROR", "NON_XML"):
                    completed.add((str(record["arsId"]), str(record["busRouteId"])))
    return completed


def build_url(endpoint: str, api_key: str, ars_id: str, route_id: str) -> str:
    key = urllib.parse.quote(api_key, safe="%")
    params = urllib.parse.urlencode({"arsId": ars_id, "busRouteId": route_id})
    return f"{endpoint}?serviceKey={key}&{params}"


def fetch(url: str, timeout: int, retries: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "dawn-mobility-data-acquisition/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(str(exc)) from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def xml_status(body: bytes) -> tuple[str, str]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return "NON_XML", "Response is not valid XML"
    code = root.findtext(".//headerCd") or root.findtext(".//resultCode") or ""
    message = root.findtext(".//headerMsg") or root.findtext(".//resultMsg") or ""
    return code, message


def write_manifest(output_dir: Path, total: int, completed: int, run_count: int, orphan_count: int) -> None:
    manifest = {
        "dataset_id": "OA-15334",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "format": "JSON Lines with raw XML response in raw_xml",
        "total_unique_request_pairs": total,
        "completed_unique_request_pairs": completed,
        "requests_added_in_last_run": run_count,
        "remaining_request_pairs": total - completed,
        "records_not_in_current_valid_pair_set": orphan_count,
        "note": "API key is intentionally excluded. Re-run the script to resume.",
    }
    temp = output_dir / "manifest.json.part"
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(output_dir / "manifest.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-snapshot-date", default="20261016")
    parser.add_argument("--snapshot-date", default=datetime.now().astimezone().strftime("%Y%m%d"))
    parser.add_argument("--max-requests", type=int, default=1000)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--stop-after-consecutive-errors", type=int, default=5)
    args = parser.parse_args()

    env = load_env(ROOT / ".env")
    endpoint = env.get("SEOUL_BUS_STATION_FIRST_LAST_API_URL", "")
    api_key = env.get("SEOUL_BUS_STATION_API_KEY", "")
    if not endpoint or not api_key:
        print("Missing SEOUL_BUS_STATION_FIRST_LAST_API_URL or SEOUL_BUS_STATION_API_KEY in .env", file=sys.stderr)
        return 2

    output_dir = ROOT / "data" / "raw" / "bus" / "OA-15334" / f"snapshot_{args.snapshot_date}"
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs = build_pairs(args.master_snapshot_date)
    recorded = completed_pairs(output_dir)
    valid_pair_keys = {(pair[0], pair[1]) for pair in pairs}
    done = recorded & valid_pair_keys
    pending = [pair for pair in pairs if (pair[0], pair[1]) not in done]
    limit = min(max(args.max_requests, 0), len(pending))
    print(f"total={len(pairs)}, already_completed={len(done)}, requesting_now={limit}", flush=True)

    added = 0
    consecutive_errors = 0
    stream = None
    stream_path: Path | None = None
    try:
        for ars_id, route_id, station_id in pending[:limit]:
            ordinal = len(done) + added + 1
            chunk_start = ((ordinal - 1) // args.chunk_size) * args.chunk_size + 1
            chunk_end = chunk_start + args.chunk_size - 1
            target_path = output_dir / f"responses_{chunk_start:06d}_{chunk_end:06d}.jsonl"
            if target_path != stream_path:
                if stream is not None:
                    stream.close()
                stream = target_path.open("a", encoding="utf-8", newline="\n")
                stream_path = target_path

            retrieved_at = datetime.now(timezone.utc).isoformat()
            try:
                body = fetch(build_url(endpoint, api_key, ars_id, route_id), args.timeout, args.retries)
                code, message = xml_status(body)
                raw_xml = body.decode("utf-8-sig", errors="replace")
                error = None
                consecutive_errors = 0 if code not in ("NON_XML", "") else consecutive_errors + 1
            except RuntimeError as exc:
                body = b""
                code, message, raw_xml, error = "REQUEST_ERROR", "", "", str(exc)
                consecutive_errors += 1

            record = {
                "arsId": ars_id,
                "busRouteId": route_id,
                "stationId": station_id,
                "retrieved_at": retrieved_at,
                "status_code": code,
                "status_message": message,
                "error": error,
                "response_sha256": hashlib.sha256(body).hexdigest(),
                "raw_xml": raw_xml,
            }
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            stream.flush()
            added += 1
            if added % 100 == 0 or added == limit:
                print(f"  completed this run: {added}/{limit}", flush=True)
            if consecutive_errors >= args.stop_after_consecutive_errors:
                print(f"Stopping after {consecutive_errors} consecutive request/response errors", file=sys.stderr)
                break
            time.sleep(max(args.delay, 0))
    finally:
        if stream is not None:
            stream.close()

    final_recorded = completed_pairs(output_dir)
    final_completed = len(final_recorded & valid_pair_keys)
    write_manifest(output_dir, len(pairs), final_completed, added, len(final_recorded - valid_pair_keys))
    return 0 if added == limit else 1


if __name__ == "__main__":
    raise SystemExit(main())
