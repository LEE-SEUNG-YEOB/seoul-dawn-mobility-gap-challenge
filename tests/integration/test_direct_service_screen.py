import json
from pathlib import Path

import pandas as pd


OUTPUT = Path("outputs/intermediate/integration")


def test_screen_has_one_row_per_demand_candidate_and_preserves_rank():
    rows = pd.read_csv(OUTPUT / "direct_service_screening.csv", dtype={"candidate_id": str})
    assert len(rows) == 100
    assert rows["candidate_id"].is_unique
    assert rows["demand_rank"].tolist() == list(range(1, 101))


def test_confirmation_is_positive_evidence_and_buffer_is_sensitivity_only():
    rows = pd.read_csv(OUTPUT / "direct_service_screening.csv")
    assert (rows["inside_confirmed_route_count"] > 0).sum() == 94
    assert (rows["buffer_500m_confirmed_route_count"] > 0).sum() == 100
    assert set(rows["screening_status"]) == {"inside_service_confirmed", "buffer_only_service_confirmed"}
    assert (rows["buffer_500m_confirmed_route_count"] >= rows["inside_confirmed_route_count"]).all()


def test_route_evidence_never_turns_unknown_cells_into_no_service():
    evidence = pd.read_csv(OUTPUT / "direct_service_route_evidence.csv")
    assert not evidence.duplicated(["candidate_id", "access_scope", "route_id"]).any()
    assert set(evidence["service_evidence_status"]) <= {
        "confirmed_positive_origin_hour", "hourly_service_unconfirmed"
    }
    assert not evidence["service_evidence_status"].str.contains("no_service").any()
    unconfirmed = evidence[evidence["service_evidence_status"].eq("hourly_service_unconfirmed")]
    assert unconfirmed["max_positive_service_days"].isna().all()


def test_summary_states_the_limited_interpretation():
    summary = json.loads((OUTPUT / "direct_service_screening_summary.json").read_text(encoding="utf-8"))
    assert summary["candidate_count"] == 100
    assert summary["inside_confirmed_candidates"] == 94
    assert summary["buffer_500m_confirmed_candidates"] == 100
    assert summary["blank_hour_semantics"].startswith("unknown")
    assert "not exact accessibility" in summary["interpretation"]
