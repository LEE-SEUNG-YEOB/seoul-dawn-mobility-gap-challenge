"""Build the limited transit-supply audit allowed by the readiness contract.

This module deliberately does not calculate reachability, service gaps, benefits,
scenario effects, or carbon effects. Missing OA-15334 pairs are unknown.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "outputs" / "intermediate" / "access"
ASSUMPTION_SET_ID = "access-technical-inventory-v1"
FIRST_BUS_SOURCE = "OA-15334"
SUBWAY_SOURCE = "data-go-15143847"

AUDIT_FIELDS = [
    "audit_id",
    "origin_id",
    "destination_id_or_stop_id",
    "service_day_type",
    "scenario",
    "arrival_deadline",
    "reachable",
    "arrival_time",
    "access_gap_status",
    "assumption_set_id",
    "source_dataset_ids",
    "route_id",
    "planned_first_time",
    "observed_first_times",
    "observed_item_count",
    "retrieved_at",
    "source_file",
    "source_line_number",
]


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _valid_hhmmss(value: str | None) -> bool:
    if not value or not re.fullmatch(r"\d{6}", value):
        return False
    hour, minute, second = int(value[:2]), int(value[2:4]), int(value[4:])
    return hour < 24 and minute < 60 and second < 60


def _clock(value: str) -> str:
    return f"{value[:2]}:{value[2:4]}:{value[4:]}"


def parse_first_bus(snapshot_dir: Path) -> tuple[list[dict], dict]:
    """Return one earliest observed planned first time per nonzero ARS-route pair."""
    pair_items: dict[tuple[str, str], list[dict]] = defaultdict(list)
    response_rows = 0
    invalid_xml = 0
    valid_items_all = 0
    invalid_time_items = 0

    for path in sorted(snapshot_dir.glob("responses_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                response_rows += 1
                response = json.loads(line)
                try:
                    root = ET.fromstring(response.get("raw_xml") or "")
                except ET.ParseError:
                    invalid_xml += 1
                    continue
                for item_node in root.findall(".//itemList"):
                    item = {child.tag: child.text or "" for child in item_node}
                    first_time = item.get("firstBusTm")
                    if not _valid_hhmmss(first_time):
                        if first_time:
                            invalid_time_items += 1
                        continue
                    valid_items_all += 1
                    ars_id = str(response.get("arsId") or item.get("arsId") or "")
                    route_id = str(response.get("busRouteId") or item.get("busRouteId") or "")
                    if not ars_id or ars_id == "0" or not route_id:
                        continue
                    pair_items[(ars_id, route_id)].append(
                        {
                            "first_time": first_time,
                            "retrieved_at": str(response.get("retrieved_at") or ""),
                            "source_file": path.relative_to(ROOT).as_posix(),
                            "source_line_number": line_number,
                        }
                    )

    rows: list[dict] = []
    for (ars_id, route_id), items in sorted(pair_items.items()):
        selected = min(items, key=lambda item: (item["first_time"], item["source_file"], item["source_line_number"]))
        observed = sorted({item["first_time"] for item in items})
        rows.append(
            {
                "audit_id": f"oa15334:{ars_id}:{route_id}",
                "origin_id": "",
                "destination_id_or_stop_id": ars_id,
                "service_day_type": "unknown",
                "scenario": "current",
                "arrival_deadline": "",
                "reachable": "",
                "arrival_time": _clock(selected["first_time"]),
                "access_gap_status": "unknown",
                "assumption_set_id": ASSUMPTION_SET_ID,
                "source_dataset_ids": FIRST_BUS_SOURCE,
                "route_id": route_id,
                "planned_first_time": _clock(selected["first_time"]),
                "observed_first_times": "|".join(_clock(value) for value in observed),
                "observed_item_count": len(items),
                "retrieved_at": selected["retrieved_at"],
                "source_file": selected["source_file"],
                "source_line_number": selected["source_line_number"],
            }
        )

    quality = {
        "response_rows": response_rows,
        "invalid_xml_responses": invalid_xml,
        "valid_first_time_items_including_zero_ars": valid_items_all,
        "invalid_nonempty_first_time_items": invalid_time_items,
        "valid_nonzero_ars_route_item_rows": sum(len(items) for items in pair_items.values()),
        "valid_nonzero_ars_route_pairs": len(rows),
        "pairs_with_multiple_valid_items": sum(len(items) > 1 for items in pair_items.values()),
        "duplicate_pair_excess_item_rows": sum(max(0, len(items) - 1) for items in pair_items.values()),
    }
    return rows, quality


def first_time_distribution(audit_rows: list[dict]) -> list[dict]:
    counts = Counter(row["planned_first_time"][:2] for row in audit_rows)
    total = len(audit_rows)
    return [
        {
            "hour": hour,
            "valid_pair_count": counts.get(hour, 0),
            "share_of_valid_pairs": round(counts.get(hour, 0) / total, 8) if total else "",
            "in_03_to_before_06_window": str(hour in {"03", "04", "05"}).lower(),
            "source_dataset_ids": FIRST_BUS_SOURCE,
        }
        for hour in [f"{value:02d}" for value in range(24)]
    ]


def observed_coverage(audit_rows: list[dict], key: str, output_key: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in audit_rows:
        grouped[str(row[key])].append(row)
    total = len(audit_rows)
    result = []
    for value, rows in sorted(grouped.items()):
        times = [row["planned_first_time"] for row in rows]
        result.append(
            {
                output_key: value,
                "observed_valid_pair_count": len(rows),
                "share_of_1947_valid_pairs": round(len(rows) / total, 8),
                "pairs_first_time_03_to_before_06": sum("03:00:00" <= time < "06:00:00" for time in times),
                "earliest_observed_first_time": min(times),
                "latest_observed_first_time": max(times),
                "denominator_scope": "valid_nonprobability_OA-15334_pairs_only",
                "missing_pairs_status": "unknown",
                "source_dataset_ids": FIRST_BUS_SOURCE,
            }
        )
    return result


def _read_json_service_rows(directory: Path, service: str) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(directory.glob("page_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(payload[service].get("row") or [])
    return rows


def bus_inventory() -> tuple[list[dict], dict]:
    route_file = ROOT / "data/raw/bus/OA-1095/서울시버스노선별정류소정보(20260902).xlsx"
    route_frame = pd.read_excel(route_file, dtype=str)
    route_id_col, node_id_col, ars_id_col = route_frame.columns[0], route_frame.columns[3], route_frame.columns[4]
    nonzero = route_frame[route_frame[ars_id_col].fillna("").ne("0") & route_frame[ars_id_col].notna()]

    station_rows = _read_json_service_rows(
        ROOT / "data/raw/bus/OA-21231/snapshot_20261016", "tbisMasterStation"
    )
    node_rows = _read_json_service_rows(
        ROOT / "data/raw/bus/OA-21233/snapshot_20261016", "masterRouteNode"
    )

    oa1095_pairs = set(zip(nonzero[route_id_col].astype(str), nonzero[ars_id_col].astype(str)))
    oa21233_pairs = {(str(row.get("RTE_ID") or ""), str(row.get("CRTR_ID") or "")) for row in node_rows}
    inventory = [
        {
            "inventory_id": "bus_route_stop_20260902",
            "mode": "bus",
            "snapshot_date": "2026-09-02",
            "record_count": len(route_frame),
            "unique_route_count": route_frame[route_id_col].nunique(dropna=True),
            "unique_stop_count": nonzero[ars_id_col].nunique(dropna=True),
            "unique_route_stop_pair_count": len(oa1095_pairs),
            "exact_duplicate_rows": int(route_frame.duplicated().sum()),
            "scope": "route-stop inventory; September-wide validity not verified",
            "source_dataset_ids": "OA-1095",
        },
        {
            "inventory_id": "bus_station_master_20261016",
            "mode": "bus",
            "snapshot_date": "2026-10-16",
            "record_count": len(station_rows),
            "unique_route_count": "",
            "unique_stop_count": len({str(row.get("CRTR_ID") or "") for row in station_rows}),
            "unique_route_stop_pair_count": "",
            "exact_duplicate_rows": len(station_rows) - len({json.dumps(row, sort_keys=True) for row in station_rows}),
            "scope": "station master inventory; historical September validity not verified",
            "source_dataset_ids": "OA-21231",
        },
        {
            "inventory_id": "bus_route_node_master_20261016",
            "mode": "bus",
            "snapshot_date": "2026-10-16",
            "record_count": len(node_rows),
            "unique_route_count": len({str(row.get("RTE_ID") or "") for row in node_rows}),
            "unique_stop_count": len({str(row.get("CRTR_ID") or "") for row in node_rows}),
            "unique_route_stop_pair_count": len(oa21233_pairs),
            "exact_duplicate_rows": len(node_rows) - len({json.dumps(row, sort_keys=True) for row in node_rows}),
            "scope": "route-node master inventory; historical September validity not verified",
            "source_dataset_ids": "OA-21233",
        },
    ]
    quality = {
        "OA-1095": {"rows": len(route_frame), "exact_duplicate_rows": int(route_frame.duplicated().sum())},
        "OA-21231": {"rows": len(station_rows)},
        "OA-21233": {"rows": len(node_rows)},
    }
    return inventory, quality


def subway_inventory(snapshot_dir: Path) -> tuple[list[dict], dict]:
    groups: dict[tuple[str, str], dict] = {}
    all_hashes: set[str] = set()
    total_rows = 0
    duplicate_rows = 0
    missing_departure_time = 0

    pattern = re.compile(r"wknd_(.+?)__dir_(.+?)__page_\d+\.json$")
    for path in sorted(snapshot_dir.glob("wknd_*__dir_*__page_*.json")):
        match = pattern.match(path.name)
        if not match:
            continue
        day_type, direction = unquote(match.group(1)), unquote(match.group(2))
        group = groups.setdefault(
            (day_type, direction),
            {"rows": 0, "dawn": 0, "trains": set(), "stations": set(), "lines": set(), "files": 0},
        )
        group["files"] += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload["response"]["body"].get("items") or {}
        rows = items.get("item") or []
        for row in rows:
            total_rows += 1
            group["rows"] += 1
            group["trains"].add(str(row.get("trainno") or ""))
            group["stations"].add(str(row.get("dptreStnCd") or row.get("stnCd") or ""))
            group["lines"].add(str(row.get("lineNm") or row.get("dptreLineNm") or ""))
            departure = str(row.get("trainDptreTm") or "")
            if not departure:
                missing_departure_time += 1
            elif "03:00:00" <= departure < "06:00:00":
                group["dawn"] += 1
            digest = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            if digest in all_hashes:
                duplicate_rows += 1
            else:
                all_hashes.add(digest)

    rows = []
    for (day_type, direction), values in sorted(groups.items()):
        rows.append(
            {
                "service_day_type": day_type,
                "direction": direction,
                "file_count": values["files"],
                "timetable_row_count": values["rows"],
                "rows_departing_03_to_before_06": values["dawn"],
                "unique_train_number_count": len(values["trains"] - {""}),
                "unique_departure_station_count": len(values["stations"] - {""}),
                "unique_line_name_count": len(values["lines"] - {""}),
                "snapshot_date": "2026-10-16",
                "search_datetime": "2026-09-15T04:30:00",
                "historical_service_verified": "false",
                "actual_operation_verified": "false",
                "source_dataset_ids": SUBWAY_SOURCE,
            }
        )
    quality = {
        "rows": total_rows,
        "exact_duplicate_rows_across_queries": duplicate_rows,
        "rows_missing_departure_time": missing_departure_time,
        "group_count": len(rows),
    }
    return rows, quality


def build(output_dir: Path = DEFAULT_OUTPUT) -> dict:
    readiness = json.loads((ROOT / "outputs/intermediate/data_audit/readiness.json").read_text(encoding="utf-8"))
    if readiness.get("mode") != "separate_only" or not readiness.get("transit_ready"):
        raise RuntimeError("This build requires the approved separate_only transit-ready contract.")
    if readiness.get("join_ready"):
        raise RuntimeError("This limited build must not run when join_ready is true.")

    first_bus_dir = ROOT / "data/raw/bus/OA-15334/snapshot_20261016"
    audit_rows, first_bus_quality = parse_first_bus(first_bus_dir)
    request_manifest = json.loads((first_bus_dir / "manifest.json").read_text(encoding="utf-8"))
    request_universe = int(request_manifest["total_unique_request_pairs"])
    completed_requests = int(request_manifest["completed_unique_request_pairs"])

    if len(audit_rows) != 1947:
        raise AssertionError(f"Expected 1,947 valid nonzero pairs, found {len(audit_rows):,}.")
    if completed_requests != 1999 or request_universe != 44735:
        raise AssertionError("OA-15334 manifest counts no longer match the approved contract.")

    route_rows = observed_coverage(audit_rows, "route_id", "route_id")
    stop_rows = observed_coverage(audit_rows, "destination_id_or_stop_id", "ars_id")
    bus_rows, bus_quality = bus_inventory()
    subway_rows, subway_quality = subway_inventory(
        ROOT / "data/raw/subway/data-go-15143847/snapshot_20261016"
    )

    _write_csv(output_dir / "transit_coverage_audit.csv", audit_rows, AUDIT_FIELDS)
    _write_csv(
        output_dir / "first_bus_time_distribution.csv",
        first_time_distribution(audit_rows),
        ["hour", "valid_pair_count", "share_of_valid_pairs", "in_03_to_before_06_window", "source_dataset_ids"],
    )
    coverage_fields = [
        "observed_valid_pair_count",
        "share_of_1947_valid_pairs",
        "pairs_first_time_03_to_before_06",
        "earliest_observed_first_time",
        "latest_observed_first_time",
        "denominator_scope",
        "missing_pairs_status",
        "source_dataset_ids",
    ]
    _write_csv(output_dir / "first_bus_coverage_by_route.csv", route_rows, ["route_id", *coverage_fields])
    _write_csv(output_dir / "first_bus_coverage_by_stop.csv", stop_rows, ["ars_id", *coverage_fields])
    _write_csv(
        output_dir / "transit_supply_inventory.csv",
        bus_rows,
        [
            "inventory_id", "mode", "snapshot_date", "record_count", "unique_route_count",
            "unique_stop_count", "unique_route_stop_pair_count", "exact_duplicate_rows", "scope",
            "source_dataset_ids",
        ],
    )
    _write_csv(
        output_dir / "subway_timetable_inventory.csv",
        subway_rows,
        [
            "service_day_type", "direction", "file_count", "timetable_row_count",
            "rows_departing_03_to_before_06", "unique_train_number_count",
            "unique_departure_station_count", "unique_line_name_count", "snapshot_date",
            "search_datetime", "historical_service_verified", "actual_operation_verified",
            "source_dataset_ids",
        ],
    )

    summary = {
        "status": "COMPLETE_LIMITED",
        "readiness_mode": "separate_only",
        "scope": "technical inventory and acquired planned timetable cases only",
        "OA-15334": {
            "completed_requests": completed_requests,
            "request_universe": request_universe,
            "completed_request_percent": completed_requests / request_universe * 100,
            "valid_nonzero_ars_route_pairs": len(audit_rows),
            "valid_pair_percent_of_request_universe": len(audit_rows) / request_universe * 100,
            "sampling": "nonprobability",
            "unacquired_pairs": "unknown",
            **first_bus_quality,
        },
        "dawn_valid_pairs_03_to_before_06": sum(
            "03:00:00" <= row["planned_first_time"] < "06:00:00" for row in audit_rows
        ),
        "bus_inventory_quality": bus_quality,
        "subway_inventory_quality": subway_quality,
        "temporal_limit": "OA-1095 is 2026-09-02; OA-21231/OA-21233/OA-15334 and subway retrieval are 2026-10-16. Historical September equivalence is unverified.",
        "operation_limit": "Planned timetable observations only; actual vehicle/train operation is not verified.",
        "unsupported": [
            "service_gap_candidates.csv", "beneficiaries", "demand_weighted_priority", "carbon_effect",
            "15_vs_30_minute_effect", "short_route_effect", "before_after_reachable_area",
        ],
        "lineage": {
            "transit_coverage_audit.csv": ["OA-15334"],
            "first_bus_time_distribution.csv": ["OA-15334"],
            "first_bus_coverage_by_route.csv": ["OA-15334"],
            "first_bus_coverage_by_stop.csv": ["OA-15334"],
            "transit_supply_inventory.csv": ["OA-1095", "OA-21231", "OA-21233"],
            "subway_timetable_inventory.csv": ["data-go-15143847"],
        },
    }
    (output_dir / "access_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = build(args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
