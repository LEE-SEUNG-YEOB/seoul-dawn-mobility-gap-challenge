import csv
from datetime import datetime
from pathlib import Path

from src.demand.run import OPTIONAL_CANDIDATE_COLUMNS, REQUIRED_CANDIDATE_COLUMNS, day_type, normalize_hour


def test_dawn_hour_filter_does_not_conflate_hhmm() -> None:
    assert [normalize_hour(v) for v in ("3", "03", "4", "04", "5", "05")] == [3, 3, 4, 4, 5, 5]
    assert normalize_hour("0300") is None
    assert normalize_hour("0520") is None
    assert normalize_hour("6") is None


def test_september_day_type_denominators() -> None:
    dates = [datetime(2026, 9, day).strftime("%Y%m%d") for day in range(1, 31)]
    assert sum(day_type(date) == "weekday" for date in dates) == 22
    assert sum(day_type(date) == "weekend" for date in dates) == 8


def test_required_candidate_schema_is_stable() -> None:
    assert REQUIRED_CANDIDATE_COLUMNS == [
        "candidate_id", "origin_id", "destination_id", "time_bin_start", "time_bin_end",
        "demand_value", "demand_unit", "demand_rank", "selection_rule", "uncertainty_flag",
        "source_dataset_ids",
    ]


def test_generated_candidate_schema_when_output_exists() -> None:
    path = Path("outputs/intermediate/demand/demand_candidates.csv")
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
            assert set(REQUIRED_CANDIDATE_COLUMNS).issubset(header)
            assert set(OPTIONAL_CANDIDATE_COLUMNS).issubset(header)


def test_generated_candidates_exclude_self_od_when_output_exists() -> None:
    path = Path("outputs/intermediate/demand/demand_candidates.csv")
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        assert all(row["origin_id"] != row["destination_id"] for row in rows)
        assert all("weekday plus weekend monthly" in row["selection_rule"] for row in rows)
