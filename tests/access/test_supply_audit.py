import csv
import json
from pathlib import Path

from src.access.build_supply_audit import AUDIT_FIELDS, _valid_hhmmss


OUTPUT = Path("outputs/intermediate/access")


def read_csv(name):
    with (OUTPUT / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_time_validation_is_strict():
    assert _valid_hhmmss("035959")
    assert _valid_hhmmss("235959")
    assert not _valid_hhmmss("246000")
    assert not _valid_hhmmss("3600")
    assert not _valid_hhmmss(None)


def test_fixed_audit_is_one_row_per_valid_pair_and_never_infers_access():
    rows = read_csv("transit_coverage_audit.csv")
    assert len(rows) == 1947
    assert set(AUDIT_FIELDS).issubset(rows[0])
    assert len({(row["destination_id_or_stop_id"], row["route_id"]) for row in rows}) == 1947
    assert {row["scenario"] for row in rows} == {"current"}
    assert {row["access_gap_status"] for row in rows} == {"unknown"}
    assert {row["reachable"] for row in rows} == {""}
    assert {row["arrival_deadline"] for row in rows} == {""}
    assert all(row["destination_id_or_stop_id"] != "0" for row in rows)


def test_contract_numbers_and_nonprobability_limit_are_explicit():
    summary = json.loads((OUTPUT / "access_summary.json").read_text(encoding="utf-8"))
    bus = summary["OA-15334"]
    assert bus["completed_requests"] == 1999
    assert bus["request_universe"] == 44735
    assert round(bus["completed_request_percent"], 4) == 4.4685
    assert bus["valid_nonzero_ars_route_pairs"] == 1947
    assert bus["sampling"] == "nonprobability"
    assert bus["unacquired_pairs"] == "unknown"


def test_no_forbidden_join_output_is_created():
    assert not (OUTPUT / "service_gap_candidates.csv").exists()
    summary = json.loads((OUTPUT / "access_summary.json").read_text(encoding="utf-8"))
    assert "service_gap_candidates.csv" in summary["unsupported"]
    assert "carbon_effect" in summary["unsupported"]


def test_inventory_counts_are_complete_and_subway_operation_is_unverified():
    inventory = {row["inventory_id"]: row for row in read_csv("transit_supply_inventory.csv")}
    assert inventory["bus_route_stop_20260902"]["record_count"] == "41688"
    assert inventory["bus_station_master_20261016"]["record_count"] == "11497"
    assert inventory["bus_route_node_master_20261016"]["record_count"] == "88729"
    subway = read_csv("subway_timetable_inventory.csv")
    assert sum(int(row["timetable_row_count"]) for row in subway) == 296720
    assert {row["actual_operation_verified"] for row in subway} == {"false"}


def test_assumptions_disable_unsupported_network_and_effect_models():
    assumptions = json.loads(Path("src/access/config/assumptions.json").read_text(encoding="utf-8"))
    for key in ["walking", "transfer", "waiting", "arrival_deadline", "service_calendar", "short_route", "carbon"]:
        assert assumptions[key]["active"] is False
