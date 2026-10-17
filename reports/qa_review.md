# 독립 최종 QA 결과

검토 기준은 커밋 `be5c37b`이며 준비 상태는 `separate_only` (`demand_ready=true`, `transit_ready=true`, `join_ready=false`)다. 분석 소스와 산출물은 수정하지 않고 OA-21220 감사, 직결 서비스 스크리닝, 최종 표·그림·GeoJSON, 문서와 재현 절차를 독립 검토했다.

## 판정

- 치명적 문제: 0건
- 중요 문제: 0건 — 발견한 매니페스트 불일치는 재생성·검증으로 해소
- 경미 문제: 0건 — 발견한 2건은 수정 후 재검증 완료
- 분석 수치·직결 판정 로직·unknown 보존·주장 범위에서는 치명적 또는 중요 오류를 발견하지 않았다.

매니페스트는 이 QA 보고서를 포함한 모든 보고서가 확정된 뒤에만 최종값을 가질 수 있다. 메인이 `provenance --write`와 verify-only 명령을 실행해 모두 `Verified 34 artifacts`, 종료 코드 0을 확인했다. 이 최종 판정 문구까지 반영한 뒤 같은 두 명령을 한 번 더 실행해 매니페스트를 고정한다.

## 발견 사항

### [중요 — 해결됨] 최종 산출물 매니페스트 재생성·검증

- 위치: `outputs/final/artifact_manifest.json`, `src/reporting/provenance.py:33-39`
- 재현: `\.venv\Scripts\python.exe -m src.reporting.provenance`
- 결과: `outputs/final/summary.json`에서 `ValueError: Artifact changed or incomplete`로 종료 코드 1이 발생했다.
- 독립 대조: 매니페스트 30개 항목 중 다음 4개가 현재 파일과 불일치했다.
  - `outputs/final/summary.json`
  - `reports/analysis_coverage.md`
  - `reports/analysis_handoff.md`
  - `reports/assumptions_and_limits.md`
- 영향: 표·수치 자체의 오류는 아니지만, 현재 커밋에 포함된 무결성 매니페스트로 최종 결과를 검증할 수 없다. README의 최종 provenance 검증 단계가 실패한다.
- 처리 상태: 분석 산출물의 결정적 재생성을 확인했고, 메인이 `\.venv\Scripts\python.exe -m src.reporting.provenance --write`와 verify-only 명령을 실행해 모두 `Verified 34 artifacts`, 종료 코드 0을 확인했다. 이 QA 문구 수정 후 매니페스트를 다시 고정하면 동일 검증 상태가 최종 커밋에 반영된다.

### [경미 — 해결됨] OA-21220 추가 수집 메타데이터

- 위치: `config/analysis.json:8`, `data/metadata/analysis_contract.json:7003`
- 최초 발견: 설정의 `new_data_collection=false`가 계약의 승인된 OA-21220 추가 수집 이력과 맞지 않았다.
- 수정·재검증: `new_data_collection=true`로 바뀌었고 `supplementary_collection="OA-21220 public unauthenticated September 2026 operation-count files only"`가 추가됐다. 계약의 수집 범위와 일치한다.

### [경미 — 해결됨] OA-21220 분석 기간 표현

- 위치: `reports/analysis_handoff.md:33`
- 최초 발견: “2026년 9월 30일의”가 9월 30일 하루 자료로 읽힐 수 있었다.
- 수정·재검증: `reports/analysis_handoff.md:33`이 “2026년 9월 한 달간”으로 수정되어 실제 범위 2026-09-01~2026-09-30과 일치한다.

## OA-21220 감사와 unknown 처리

- 분석 기간: 2026-09-01~2026-09-30, 관측일 30일
- 원자료 행: 2,638,894행
- 업무키 중복 초과: 0행, 완전 중복: 0행
- 수치형 비정상·음수: 0건
- 일별 총 운행횟수 결측: 35,474행
- 일별 총계와 관측 시간셀 합 불일치: 19,161행
- 시간셀 결측: 03시 2,552,937개, 04시 2,163,808개, 05시 1,349,252개
- 양수 운행 증거 출력: 72,024개 `route_id × stop_id × stop_sequence × hour` 조합
- 양수 관측이 전혀 없는 217,551개 조합은 compact evidence에서 제외되지만 서비스 없음으로 판정하지 않는다.
- 출력의 `blank_cell_days`, `missing_row_days`, `unknown_days`가 별도 보존되며 빈 셀이나 누락 행을 0·무운행·`no_gap`으로 바꾸지 않는다.

## 직결 서비스 스크리닝 로직과 결과

코드와 산출물을 대조해 다음 조건을 확인했다.

1. 출발·목적지에 같은 `route_id`가 존재해야 한다.
2. 출발 정류소 `stop_sequence`가 같은 노선의 목적지 최대 순서보다 작아야 한다.
3. 후보의 출발 시간대와 동일한 시간에서 출발 정류소의 OA-21220 양수 운행 관측이 있어야 `confirmed`다.
4. 행정동 내부 `inside`와 행정동 경계 500m 완충 `buffer_500m`를 별도 계산한다. 완충 결과는 내부를 포함한 민감도 기준이다.

최종 결과는 100행이며 수요 순위 1~100을 보존한다.

- `inside_service_confirmed`: 94개
- `buffer_only_service_confirmed`: 6개
- 500m 이내 양수 증거 확인: 100개
- `service_unconfirmed_within_500m`: 0개
- 경로 증거: 4,698행, `candidate_id × access_scope × route_id` 중복 0건
- 확인 증거 행: 3,328개, 시간대 운행 미확인 행: 1,370개
- 공간 입력: inside 28,084행, buffer-only 59,171행
- inside 거리는 모두 0m, buffer-only 거리는 0.126~499.487m

중간·최종 `direct_service_screening.csv`와 `direct_service_route_evidence.csv`는 각각 바이트 단위로 동일하며 필수 키와 상태 열의 공란이 없다.

## 주장 범위와 시각·공간 산출물

- README, handoff, coverage, limits, 요약 JSON과 표 주석은 결과를 직결 서비스 **존재 증거 스크리닝**으로 제한한다.
- 정확한 탑승 가능, 동일 차량의 완주, 정확한 도착시각, 배차간격, 보행 접근성, 환승 성공, 서비스 충분성, 서비스 공백과 정책 우선순위를 계산했다고 주장하지 않는다.
- 500m는 개인 보행거리 판정이 아니라 행정동 경계 민감도임을 명시한다.
- `direct_service_screening.png`는 제목, 축, 20개 OD 레이블, 내부·500m 범례와 한계 주석이 잘리지 않고 판독 가능하다.
- `direct_service_screening.geojson`은 100개 `LineString`이며 각 선은 좌표 2개만 가진다. 모든 feature의 `geometry_note`가 `straight representative-point connector; not a bus path`이고 README와 handoff도 실제 버스 경로가 아님을 고지한다.

## 실행한 검증

- `\.venv\Scripts\python.exe -m pytest -q --basetemp=outputs/tmp/pytest_qa_final` → **39 passed**
- `tests/data` → 11 passed
- `tests/demand` → 10 passed
- `tests/access` → 9 passed
- `tests/integration` → 9 passed
- `\.venv\Scripts\python.exe -m src.data.validate_contract --contract data/metadata/analysis_contract.json --verify-hashes` → 19개 데이터셋 전체 해시 검증 통과
- `src.access.build_observed_bus_service`, `src.demand.direct_service_inputs`, `src.integration.build_direct_service_screen`, `src.reporting.build_report` 순차 재실행 → 모두 종료 코드 0
- 재생성 후 `git status --short` 무출력, `git diff --check` 통과 → 추적 산출물의 결정적 재생성 확인
- `data/`, `.env`, `.venv/`, `AGENTS.md`, `.agents/`, `prompts/`가 Git 무시 대상이고 추적된 원자료·인증정보가 없음을 확인
- 최초 `\.venv\Scripts\python.exe -m src.reporting.provenance` → 불일치 4개를 발견해 종료 코드 1
- 수정 후 `\.venv\Scripts\python.exe -m src.reporting.provenance --write` 및 verify-only → 각각 **Verified 34 artifacts**, 종료 코드 0

## 결론

OA-21220 감사 수치, blank=`unknown` 처리, 직결 판정식, 94/6/100/0 결과, 출력 스키마, 시각 자료와 제한적 해석은 서로 일치한다. 중요 지적 1건과 경미 지적 2건은 모두 수정·재검증됐다. 준비 상태 `separate_only`와 최종 상태 `COMPLETE_LIMITED`는 적절하며 최종 QA를 통과한다.
