import json
from pathlib import Path

import pandas as pd

from src.access.build_observed_bus_service import KEY_COLUMNS, aggregate_chunk


OUTPUT = Path("outputs/intermediate/access/observed_bus_service.csv")
SUMMARY = Path("outputs/intermediate/access/observed_bus_service_summary.json")


def test_blank_cells_remain_unknown_in_chunk_aggregation():
    frame = pd.DataFrame(
        {
            "date": ["20260901", "20260905"],
            "route_id": ["R1", "R1"],
            "stop_id": ["S1", "S1"],
            "stop_sequence": ["2", "2"],
            "hour_03": ["2", None],
            "hour_04": [None, None],
            "hour_05": ["1", "3"],
        }
    )
    result, invalid = aggregate_chunk(frame)
    assert invalid == 0
    hour03 = result[result["hour"] == "03"].iloc[0]
    assert hour03["positive_service_days"] == 1
    assert hour03["observed_trip_count_sum"] == 2
    assert hour03["blank_cell_days"] == 1
    hour04 = result[result["hour"] == "04"].iloc[0]
    assert hour04["positive_service_days"] == 0
    assert hour04["blank_cell_days"] == 2


def test_output_grain_and_positive_evidence_rule():
    data = pd.read_csv(OUTPUT, dtype={column: str for column in KEY_COLUMNS})
    assert not data.duplicated(KEY_COLUMNS).any()
    assert set(data["hour"]) == {"03", "04", "05"}
    assert (data["positive_service_days"] > 0).all()
    assert data["service_confirmed"].all()
    assert (
        data["positive_service_days"]
        == data["positive_weekday_days"] + data["positive_weekend_days"]
    ).all()
    assert (data["unknown_days"] == data["blank_cell_days"] + data["missing_row_days"]).all()
    assert (data["observed_row_days"] + data["missing_row_days"] == 30).all()
    assert set(data["source_dataset_ids"]) == {"OA-21220"}


def test_summary_confirms_date_filter_duplicates_and_unknown_semantics():
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["analysis_period"] == {
        "start": "2026-09-01",
        "end": "2026-09-30",
        "observed_days": 30,
    }
    assert summary["source_september_rows"] == 2_638_894
    assert summary["source_duplicate_business_key_excess"] == 0
    assert summary["source_duplicate_rows"] == 0
    assert summary["invalid_nonblank_dawn_cells"] == 0
    assert summary["blank_cell_semantics"].startswith("unknown")
    assert summary["missing_daily_row_semantics"].startswith("unknown")
    assert summary["confirmed_output_rows"] > 0
    assert summary["all_unknown_key_hour_combinations_excluded"] > 0
    assert summary["source_dawn_cell_totals"]["03"]["blank_cells"] == 2_552_937
    assert summary["source_dawn_cell_totals"]["04"]["blank_cells"] == 2_163_808
    assert summary["source_dawn_cell_totals"]["05"]["blank_cells"] == 1_349_252

