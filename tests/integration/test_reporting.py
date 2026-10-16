import json
from pathlib import Path
import pandas as pd

from src.reporting.build_report import build


def test_limited_report_preserves_separate_axes():
    summary = build()
    assert summary['status'] == 'COMPLETE_LIMITED'
    assert summary['readiness_mode'] == 'separate_only'
    assert summary['join_ready'] is False
    assert not Path('outputs/intermediate/access/service_gap_candidates.csv').exists()
    audit = pd.read_csv('outputs/final/tables/transit_coverage_audit.csv', keep_default_na=False)
    assert len(audit) == 1947
    assert set(audit.access_gap_status) == {'unknown'}
    assert not audit.reachable.any()


def test_maps_and_figures_are_complete():
    build()
    geo = json.loads(Path('outputs/final/maps/dong_demand.geojson').read_text(encoding='utf-8'))
    assert len(geo['features']) == 426
    assert sum(f['properties']['mobility_id'] is not None for f in geo['features']) == 425
    assert all(Path(p).stat().st_size > 10_000 for p in [
        'outputs/final/figures/hour_day_type.png',
        'outputs/final/figures/top_od_candidates.png',
        'outputs/final/figures/origin_demand_map.png',
        'outputs/final/figures/destination_demand_map.png'])
