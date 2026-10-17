"""Aggregate September OA-21220 observed bus runs for dawn screening.

The output contains only route-stop-sequence-hour combinations with at least
one strictly positive observed run count. Blank cells and absent daily rows are
counted as unknown and are never converted into evidence of zero service.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "bus" / "OA-21220" / "extracted"
AUDIT_PATH = ROOT / "outputs" / "intermediate" / "data_audit" / "OA-21220_audit.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "intermediate" / "access" / "observed_bus_service.csv"
DEFAULT_SUMMARY = ROOT / "outputs" / "intermediate" / "access" / "observed_bus_service_summary.json"

SEPTEMBER_DATES = {f"202609{day:02d}" for day in range(1, 31)}
KEY_COLUMNS = ["route_id", "stop_id", "stop_sequence", "hour"]
METRIC_COLUMNS = [
    "observed_row_days",
    "positive_service_days",
    "positive_weekday_days",
    "positive_weekend_days",
    "observed_trip_count_sum",
    "blank_cell_days",
]
OUTPUT_COLUMNS = [
    *KEY_COLUMNS,
    "service_confirmed",
    "positive_service_days",
    "positive_weekday_days",
    "positive_weekend_days",
    "observed_trip_count_sum",
    "blank_cell_days",
    "missing_row_days",
    "unknown_days",
    "observed_row_days",
    "expected_september_days",
    "day_type_definition",
    "source_dataset_ids",
]


def _read_chunk_frames(path: Path, chunk_size: int):
    """Yield normalized seven-column chunks using stable source positions.

    The provider CSV headers are mojibake in the local extracts, while the
    audited positional schema is stable. Positions are validated against the
    29-column audit before this function is used.
    """
    usecols = [0, 1, 2, 7, 8, 9, 28]
    names = ["date", "route_id", "stop_id", "hour_03", "hour_04", "hour_05", "stop_sequence"]
    for chunk in pd.read_csv(
        path,
        encoding="cp949",
        dtype=str,
        usecols=usecols,
        chunksize=chunk_size,
        low_memory=False,
    ):
        chunk.columns = names
        yield chunk


def aggregate_chunk(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Aggregate one normalized daily chunk, preserving blank-cell counts."""
    frame = frame[frame["date"].isin(SEPTEMBER_DATES)].copy()
    if frame.empty:
        return pd.DataFrame(columns=[*KEY_COLUMNS, *METRIC_COLUMNS]), 0

    parsed_dates = pd.to_datetime(frame["date"], format="%Y%m%d", errors="raise")
    weekday = parsed_dates.dt.dayofweek.lt(5)
    parts = []
    invalid_cells = 0
    for hour in (3, 4, 5):
        raw = frame[f"hour_{hour:02d}"]
        blank = raw.isna() | raw.str.strip().eq("")
        numeric = pd.to_numeric(raw.where(~blank), errors="coerce")
        invalid = (~blank) & numeric.isna()
        invalid_cells += int(invalid.sum())
        if (numeric.dropna() < 0).any():
            raise AssertionError("Negative dawn run count found in OA-21220.")

        positive = numeric.gt(0)
        part = frame[["route_id", "stop_id", "stop_sequence"]].copy()
        part["hour"] = f"{hour:02d}"
        part["observed_row_days"] = 1
        part["positive_service_days"] = positive.astype("int64")
        part["positive_weekday_days"] = (positive & weekday).astype("int64")
        part["positive_weekend_days"] = (positive & ~weekday).astype("int64")
        # fillna(0) is used only for an arithmetic sum paired with an explicit
        # blank count. It does not turn a blank observation into zero service.
        part["observed_trip_count_sum"] = numeric.fillna(0).astype("int64")
        part["blank_cell_days"] = blank.astype("int64")
        parts.append(part)

    long = pd.concat(parts, ignore_index=True)
    grouped = long.groupby(KEY_COLUMNS, as_index=False, sort=False)[METRIC_COLUMNS].sum()
    return grouped, invalid_cells


def _merge_aggregates(current: pd.DataFrame | None, addition: pd.DataFrame) -> pd.DataFrame:
    if current is None or current.empty:
        return addition
    combined = pd.concat([current, addition], ignore_index=True)
    return combined.groupby(KEY_COLUMNS, as_index=False, sort=False)[METRIC_COLUMNS].sum()


def build(
    output_path: Path = DEFAULT_OUTPUT,
    summary_path: Path = DEFAULT_SUMMARY,
    chunk_size: int = 250_000,
) -> dict:
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    september_audit = audit["september"]
    if september_audit["duplicate_key_excess"] != 0 or september_audit["duplicate_rows"] != 0:
        raise AssertionError("OA-21220 audit reports duplicate September source rows.")
    if september_audit["row_count"] != 2_638_894:
        raise AssertionError("OA-21220 September row count differs from the approved audit.")
    if september_audit["column_stats"]["기준_날짜"] != {"missing": 0, "min": "20260901", "max": "20260930"}:
        raise AssertionError("OA-21220 September date audit is not the expected complete date range.")

    aggregate: pd.DataFrame | None = None
    source_rows = 0
    invalid_dawn_cells = 0
    observed_dates: set[str] = set()
    input_files = sorted(RAW_DIR.glob("*.csv"))
    for path in input_files:
        for chunk in _read_chunk_frames(path, chunk_size):
            september = chunk[chunk["date"].isin(SEPTEMBER_DATES)]
            source_rows += len(september)
            observed_dates.update(september["date"].dropna().unique())
            addition, invalid = aggregate_chunk(chunk)
            invalid_dawn_cells += invalid
            aggregate = _merge_aggregates(aggregate, addition)

    if aggregate is None:
        raise AssertionError("No OA-21220 September rows were read.")
    if source_rows != september_audit["row_count"]:
        raise AssertionError(f"Expected 2,638,894 September rows, read {source_rows:,}.")
    if observed_dates != SEPTEMBER_DATES:
        raise AssertionError("OA-21220 input does not contain exactly all 30 September dates.")
    if invalid_dawn_cells:
        raise AssertionError(f"Found {invalid_dawn_cells:,} invalid nonblank dawn cells.")

    aggregate["missing_row_days"] = 30 - aggregate["observed_row_days"]
    if (aggregate["missing_row_days"] < 0).any():
        raise AssertionError("A source business key occurs more than once on at least one date.")
    aggregate["unknown_days"] = aggregate["blank_cell_days"] + aggregate["missing_row_days"]

    all_key_hours = len(aggregate)
    all_unknown_key_hours = int((aggregate["positive_service_days"] == 0).sum())
    source_dawn_cell_totals = {}
    for hour, rows in aggregate.groupby("hour", sort=True):
        expected_blank = int(september_audit["column_stats"][f"버스운행횟수_{hour}시"]["missing"])
        observed_blank = int(rows["blank_cell_days"].sum())
        if observed_blank != expected_blank:
            raise AssertionError(
                f"Hour {hour} blank count {observed_blank:,} differs from audited {expected_blank:,}."
            )
        source_dawn_cell_totals[str(hour)] = {
            "positive_cells": int(rows["positive_service_days"].sum()),
            "blank_cells": observed_blank,
            "observed_trip_count_sum": int(rows["observed_trip_count_sum"].sum()),
        }
    result = aggregate[aggregate["positive_service_days"] > 0].copy()
    result["service_confirmed"] = True
    result["expected_september_days"] = 30
    result["day_type_definition"] = "calendar_Mon-Fri_vs_Sat-Sun_not_holiday_adjusted"
    result["source_dataset_ids"] = "OA-21220"
    result["_sequence_numeric"] = pd.to_numeric(result["stop_sequence"], errors="coerce")
    result = result.sort_values(
        ["route_id", "_sequence_numeric", "stop_sequence", "stop_id", "hour"],
        kind="stable",
    ).drop(columns="_sequence_numeric")

    if result.duplicated(KEY_COLUMNS).any():
        raise AssertionError("Duplicate output grain found.")
    if not (
        result["positive_service_days"]
        == result["positive_weekday_days"] + result["positive_weekend_days"]
    ).all():
        raise AssertionError("Weekday/weekend positive-day counts do not reconcile.")
    if (result["observed_trip_count_sum"] < result["positive_service_days"]).any():
        raise AssertionError("Positive day counts exceed observed trip counts.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result[OUTPUT_COLUMNS].to_csv(output_path, index=False, encoding="utf-8-sig")

    by_hour = {}
    for hour, rows in result.groupby("hour", sort=True):
        by_hour[str(hour)] = {
            "confirmed_route_stop_sequence_count": int(len(rows)),
            "unique_route_count": int(rows["route_id"].nunique()),
            "unique_stop_id_count": int(rows["stop_id"].nunique()),
            "positive_service_day_sum": int(rows["positive_service_days"].sum()),
            "observed_trip_count_sum": int(rows["observed_trip_count_sum"].sum()),
            "blank_cell_day_sum_among_confirmed_keys": int(rows["blank_cell_days"].sum()),
            "unknown_day_sum_among_confirmed_keys": int(rows["unknown_days"].sum()),
        }

    summary = {
        "dataset_id": "OA-21220",
        "status": "limited_actual_run_direct_service_screening",
        "analysis_period": {"start": "2026-09-01", "end": "2026-09-30", "observed_days": 30},
        "hours": [3, 4, 5],
        "source_file_count": len(input_files),
        "source_september_rows": source_rows,
        "source_duplicate_business_key_excess": int(september_audit["duplicate_key_excess"]),
        "source_duplicate_rows": int(september_audit["duplicate_rows"]),
        "invalid_nonblank_dawn_cells": invalid_dawn_cells,
        "all_observed_key_hour_combinations": all_key_hours,
        "confirmed_output_rows": int(len(result)),
        "all_unknown_key_hour_combinations_excluded": all_unknown_key_hours,
        "source_dawn_cell_totals": source_dawn_cell_totals,
        "output_grain": "route_id x stop_id x stop_sequence x hour",
        "service_confirmation_rule": "at least one strictly positive OA-21220 run count during September 2026",
        "blank_cell_semantics": "unknown; never zero or no-service",
        "missing_daily_row_semantics": "unknown; never zero or no-service",
        "day_type_definition": "calendar Monday-Friday versus Saturday-Sunday; not holiday adjusted",
        "stop_sequence": "OA-21220 source value preserved; no external route/stop-name join",
        "by_hour": by_hour,
        "limitations": [
            "Positive hourly counts confirm only direct service was recorded at the route-stop-sequence-hour grain.",
            "Hourly aggregates do not establish exact first arrival, trip travel time, transfers, walking access, or deadline reachability.",
            "Blank cells, missing daily rows, and excluded all-unknown key-hours do not prove absence of service.",
            "The output is not a service-gap, demand, beneficiary, priority, scenario, or causal result.",
        ],
        "source": {
            "provider": "서울특별시",
            "dataset_id": "OA-21220",
            "source_url": audit["source_url"],
            "retrieved_at": audit["retrieved_at"],
            "license": audit["license"],
            "audit": AUDIT_PATH.relative_to(ROOT).as_posix(),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--chunk-size", type=int, default=250_000)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.summary, args.chunk_size), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

