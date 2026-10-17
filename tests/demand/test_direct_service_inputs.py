import csv
from pathlib import Path

from shapely.geometry import Point, Polygon

from src.demand.direct_service_inputs import (
    OUTPUT_COLUMNS,
    coordinate_statuses,
    spatial_relation,
)


def test_spatial_relation_distinguishes_inside_buffer_and_outside() -> None:
    polygon = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    assert spatial_relation(polygon, Point(50, 50)) == ("inside", 0.0)
    relation, distance = spatial_relation(polygon, Point(350, 50))
    assert relation == "buffer_500m"
    assert distance == 250.0
    relation, distance = spatial_relation(polygon, Point(700, 50))
    assert relation is None
    assert distance == 600.0


def test_coordinate_statuses_preserve_missing_and_ambiguous() -> None:
    rows = [
        {"stop_id": "unique", "longitude": 127.0, "latitude": 37.5},
        {"stop_id": "ambiguous", "longitude": 127.0, "latitude": 37.5},
        {"stop_id": "ambiguous", "longitude": 127.1, "latitude": 37.5},
        {"stop_id": "missing", "longitude": None, "latitude": 37.5},
    ]
    assert coordinate_statuses(rows) == {
        "unique": "unique",
        "ambiguous": "unknown_ambiguous_coordinate",
        "missing": "unknown_missing_coordinate",
    }


def test_generated_output_schema_and_distance_bounds_when_present() -> None:
    path = Path("outputs/intermediate/demand/direct_service_candidate_stops.csv")
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == OUTPUT_COLUMNS
        rows = list(reader)
    assert rows
    selected = [row for row in rows if row["inside_or_buffer"] in {"inside", "buffer_500m"}]
    assert selected
    assert all(0 <= float(row["distance_to_polygon_m"]) <= 500 for row in selected)
    assert all(float(row["distance_to_polygon_m"]) == 0 for row in selected if row["inside_or_buffer"] == "inside")
    assert {row["endpoint_role"] for row in selected} == {"origin", "destination"}


def test_generated_common_route_flags_follow_endpoint_route_sets_when_present() -> None:
    path = Path("outputs/intermediate/demand/direct_service_candidate_stops.csv")
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_candidate: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_candidate.setdefault(row["candidate_id"], []).append(row)
    for candidate_rows in by_candidate.values():
        origin_routes = {row["route_id"] for row in candidate_rows if row["endpoint_role"] == "origin"}
        destination_routes = {row["route_id"] for row in candidate_rows if row["endpoint_role"] == "destination"}
        common_routes = origin_routes & destination_routes
        assert all(
            (row["route_present_at_both_endpoints"] == "true") == (row["route_id"] in common_routes)
            for row in candidate_rows
        )
