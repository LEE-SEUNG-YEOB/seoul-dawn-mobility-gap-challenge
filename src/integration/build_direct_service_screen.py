"""Build a limited direct-bus-service evidence screen for the top demand ODs.

The output confirms only that a positive OA-21220 hourly run count was observed
at an origin-side stop on a route whose audited stop order later reaches a
destination-side stop. It does not establish a particular trip, travel time,
arrival deadline, transfer path, individual walking access, or service gap.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEMAND = ROOT / "outputs" / "intermediate" / "demand"
ACCESS = ROOT / "outputs" / "intermediate" / "access"
OUTPUT = ROOT / "outputs" / "intermediate" / "integration"
SOURCE_IDS = "OA-22300|OA-1095|OA-21220|data-go-15129688"


def _scope_route_evidence(stops: pd.DataFrame, service: pd.DataFrame, scope: str) -> pd.DataFrame:
    scoped = stops if scope == "buffer_500m" else stops[stops["inside_or_buffer"].eq("inside")]
    origins = scoped[scoped["endpoint_role"].eq("origin")].copy()
    destinations = scoped[scoped["endpoint_role"].eq("destination")].copy()

    destination_stats = (
        destinations.groupby(["candidate_id", "route_id"], as_index=False)
        .agg(max_destination_sequence=("stop_sequence", "max"), destination_access_stop_count=("stop_id", "nunique"))
    )
    eligible = origins.merge(destination_stats, on=["candidate_id", "route_id"], how="inner", validate="many_to_one")
    eligible = eligible[eligible["stop_sequence"] < eligible["max_destination_sequence"]].copy()
    eligible["hour"] = eligible["time_bin_start"].str[:2].astype(int)

    service_columns = [
        "route_id", "stop_id", "stop_sequence", "hour", "positive_service_days",
        "positive_weekday_days", "positive_weekend_days", "observed_trip_count_sum",
        "unknown_days",
    ]
    eligible = eligible.merge(
        service[service_columns], on=["route_id", "stop_id", "stop_sequence", "hour"], how="left",
        validate="many_to_one",
    )
    eligible["service_confirmed"] = eligible["positive_service_days"].notna()

    def summarize(group: pd.DataFrame) -> pd.Series:
        confirmed = group[group["service_confirmed"]]
        name = sorted(group["route_name"].dropna().astype(str).unique())
        return pd.Series(
            {
                "route_name": name[0] if name else "",
                "hour": int(group["hour"].iloc[0]),
                "origin_access_stop_count": int(group["stop_id"].nunique()),
                "destination_access_stop_count": int(group["destination_access_stop_count"].max()),
                "confirmed_origin_stop_count": int(confirmed["stop_id"].nunique()),
                "max_positive_service_days": int(confirmed["positive_service_days"].max()) if not confirmed.empty else pd.NA,
                "max_positive_weekday_days": int(confirmed["positive_weekday_days"].max()) if not confirmed.empty else pd.NA,
                "max_positive_weekend_days": int(confirmed["positive_weekend_days"].max()) if not confirmed.empty else pd.NA,
                "max_observed_trip_count_at_one_stop": int(confirmed["observed_trip_count_sum"].max()) if not confirmed.empty else pd.NA,
                "min_unknown_days_at_confirmed_stop": int(confirmed["unknown_days"].min()) if not confirmed.empty else pd.NA,
                "service_evidence_status": "confirmed_positive_origin_hour" if not confirmed.empty else "hourly_service_unconfirmed",
            }
        )

    evidence = (
        eligible.groupby(["candidate_id", "route_id"], sort=True, group_keys=False)
        .apply(summarize, include_groups=False)
        .reset_index()
    )
    evidence.insert(1, "access_scope", scope)
    evidence["night_route_flag"] = evidence["route_name"].str.upper().str.startswith("N")
    evidence["autonomous_route_flag"] = evidence["route_name"].str.upper().str.startswith("A")
    evidence["source_dataset_ids"] = SOURCE_IDS
    evidence["uncertainty_flag"] = (
        "positive origin-stop hourly count plus downstream route inventory only; exact trip, travel time, "
        "arrival, transfer, and individual walking access unverified; blank OA-21220 cells remain unknown"
    )
    return evidence


def build(output_dir: Path = OUTPUT) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates = pd.read_csv(DEMAND / "demand_candidates.csv", dtype={"candidate_id": str})
    stops = pd.read_csv(
        DEMAND / "direct_service_candidate_stops.csv",
        dtype={"candidate_id": str, "route_id": str, "stop_id": str, "ars_id": str},
    )
    service = pd.read_csv(
        ACCESS / "observed_bus_service.csv",
        dtype={"route_id": str, "stop_id": str},
    )
    stops["stop_sequence"] = pd.to_numeric(stops["stop_sequence"], errors="raise").astype(int)
    service["stop_sequence"] = pd.to_numeric(service["stop_sequence"], errors="raise").astype(int)
    service["hour"] = pd.to_numeric(service["hour"], errors="raise").astype(int)

    inside = _scope_route_evidence(stops, service, "inside")
    buffered = _scope_route_evidence(stops, service, "buffer_500m")
    evidence = pd.concat([inside, buffered], ignore_index=True).sort_values(
        ["candidate_id", "access_scope", "route_id"]
    )

    def candidate_scope_summary(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        rows = []
        for candidate_id, group in frame.groupby("candidate_id"):
            confirmed = group[group["service_evidence_status"].eq("confirmed_positive_origin_hour")]
            rows.append(
                {
                    "candidate_id": candidate_id,
                    f"{prefix}_direction_compatible_route_count": int(group["route_id"].nunique()),
                    f"{prefix}_confirmed_route_count": int(confirmed["route_id"].nunique()),
                    f"{prefix}_confirmed_night_route_count": int(confirmed.loc[confirmed["night_route_flag"], "route_id"].nunique()),
                    f"{prefix}_confirmed_autonomous_route_count": int(confirmed.loc[confirmed["autonomous_route_flag"], "route_id"].nunique()),
                    f"{prefix}_confirmed_route_ids": "|".join(sorted(confirmed["route_id"].astype(str).unique())),
                    f"{prefix}_confirmed_route_names": "|".join(sorted(confirmed["route_name"].astype(str).unique())),
                    f"{prefix}_max_positive_service_days": int(confirmed["max_positive_service_days"].max()) if not confirmed.empty else pd.NA,
                }
            )
        return pd.DataFrame(rows)

    summary = candidates.merge(candidate_scope_summary(inside, "inside"), on="candidate_id", how="left")
    summary = summary.merge(candidate_scope_summary(buffered, "buffer_500m"), on="candidate_id", how="left")
    count_columns = [column for column in summary if column.endswith("_count")]
    summary[count_columns] = summary[count_columns].fillna(0).astype(int)
    summary["screening_status"] = "service_unconfirmed_within_500m"
    summary.loc[summary["buffer_500m_confirmed_route_count"].gt(0), "screening_status"] = "buffer_only_service_confirmed"
    summary.loc[summary["inside_confirmed_route_count"].gt(0), "screening_status"] = "inside_service_confirmed"
    summary["screening_interpretation"] = summary["screening_status"].map(
        {
            "inside_service_confirmed": "positive hourly direct-route evidence at a stop inside both endpoint dongs",
            "buffer_only_service_confirmed": "positive hourly direct-route evidence only after applying the 500 m dong-boundary buffer",
            "service_unconfirmed_within_500m": "no positive direct-route evidence found within the screen; absence of service is not established",
        }
    )
    summary["source_dataset_ids"] = SOURCE_IDS
    summary["uncertainty_flag"] = (
        "dong-level screen; 500 m is not an individual walk test; destination arrival time and trip identity "
        "unverified; OA-21220 blanks are unknown; result is not a service-gap or priority finding"
    )
    summary = summary.sort_values("demand_rank")

    summary.to_csv(output_dir / "direct_service_screening.csv", index=False, encoding="utf-8-sig")
    evidence.to_csv(output_dir / "direct_service_route_evidence.csv", index=False, encoding="utf-8-sig")

    status_counts = summary["screening_status"].value_counts().sort_index().to_dict()
    result = {
        "status": "COMPLETE_LIMITED_DIRECT_SERVICE_SCREEN",
        "candidate_count": int(len(summary)),
        "route_evidence_rows": int(len(evidence)),
        "status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "inside_confirmed_candidates": int(summary["inside_confirmed_route_count"].gt(0).sum()),
        "buffer_500m_confirmed_candidates": int(summary["buffer_500m_confirmed_route_count"].gt(0).sum()),
        "unconfirmed_within_500m_candidates": int(summary["buffer_500m_confirmed_route_count"].eq(0).sum()),
        "method": "positive origin-stop hourly run evidence plus downstream stop order on the same route",
        "access_scopes": ["administrative-dong interior", "administrative-dong polygon buffered 500 m"],
        "blank_hour_semantics": "unknown; never zero or no-service",
        "interpretation": "direct-service presence screen only; not exact accessibility, service gap, unmet demand, or policy priority",
        "source_dataset_ids": SOURCE_IDS,
    }
    (output_dir / "direct_service_screening_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "direct_service_screening_notes.md").write_text(
        """# 직결 버스 서비스 스크리닝 방법

상위 100개 OD-hour 수요 후보의 출발·도착 행정동 내부 정류소와, 행정동 경계를 미터 좌표계에서 500m 확장한 정류소를 각각 비교했다. 같은 노선에서 출발 정류소 순서가 도착 정류소보다 앞서고, 출발 시간대에 OA-21220 양수 운행횟수가 한 번 이상 관측된 경우만 `confirmed`로 분류했다.

행정동 내부 결과를 엄격 기준, 500m 완충 결과를 민감도 기준으로 함께 제시한다. 500m는 개인별 보행 접근성 기준이 아니다. 운행횟수는 시간 단위 집계이므로 특정 차량이 도착 정류소까지 운행했는지, 실제 도착시각, 환승 성공, 배차 대기, 만차·결행 또는 도착 마감 충족 여부를 입증하지 않는다. OA-21220 빈 셀과 누락 행은 `unknown`이며 서비스 없음으로 바꾸지 않았다. 따라서 결과는 직결 서비스 존재 증거를 찾는 후보 스크리닝이고, 서비스 공백·미충족 수요·노선 우선순위 판정이 아니다.
""",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
