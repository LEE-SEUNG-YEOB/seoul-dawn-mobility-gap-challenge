# transit_access_analyst 역할

## 임무

노선, 정류장별 첫차, 환승, 보행을 반영해 새벽 대중교통 접근성을 계산하고 정책 시나리오의 정량 차이를 분석한다.

## 주요 질문

- 이동 수요가 있지만 현행 대중교통으로 필요한 시각에 도착하기 어려운 OD는 어디인가?
- 첫차 15분·30분 조정과 단축노선 추가가 접근 가능 지역과 수혜 인원을 얼마나 바꾸는가?
- 차량 운행시간 대비 효과가 큰 후보 노선·정류장은 어디인가?

## 전용 수정 경로

- `src/access/`
- `tests/access/`
- `notebooks/20_access_*`
- `outputs/intermediate/access/`

공통 설정, 최종 결과, 다른 역할의 전용 경로는 수정하지 않는다. 변경이 필요하면 메인에 제안한다.

## 산출물

- 정류장별 첫차·환승·보행을 포함한 도착 가능성 계산
- 현행 대비 15분·30분 조정과 단축노선 시나리오
- 시나리오별 예상 수혜 인원, 접근 가능 지역 변화, 운행시간 대비 효과
- 후보 노선·정류장 결과표와 지도용 파일
- 교통수단 전환율별 탄소 변화 민감도 계산 입력·식·결과
- 주요 가정을 외부 설정으로 분리한 재현 코드와 테스트

고정 산출물 `outputs/intermediate/access/service_gap_candidates.csv`에는 최소한 `candidate_id`, `scenario`, `service_day_type`, `arrival_deadline`, `current_reachable`, `scenario_reachable`, `arrival_time`, `beneficiary_estimate`, `vehicle_hours`, `access_gap_status`, `assumption_set_id`가 있어야 한다. `access_gap_status`는 `gap|no_gap|unknown` 중 하나다.

역할 전용 가정은 `src/access/config/`에 둔다. 최소한 보행속도, 접근 반경, 환승시간, 대기시간, 도착 마감시각, 정차·회차시간, 서비스 요일, 탄소 배출계수와 출처를 외부화한다.

## 입력 게이트와 검증 명령

- 시작 전에 `data/metadata/analysis_contract.json`, `outputs/intermediate/data_audit/readiness.json`, 가능한 경우 `outputs/intermediate/demand/demand_candidates.csv`를 읽는다.
- `transit_ready=false`이면 실제 서비스 공백 계산을 하지 않고 코드·테스트·차단 근거만 만든다.
- `join_ready=false`이면 수혜 인원, 수요 가중 우선순위와 탄소 전환 효과를 만들지 않고 `unsupported`로 기록한다.
- `python -m pytest tests/access -q`가 종료 코드 0이어야 한다.

## 필수 주의사항

- 기점 첫차 출발시각만 쓰지 않고 정류장별 첫차 도착 예정시각을 사용한다.
- 계획 시각과 실제 운행 실적을 구분한다.
- 보행속도, 접근 반경, 최소 환승시간, 대기시간, 도착 마감시각을 설정 파일로 외부화한다.
- 좌표계, 날짜·요일, 공휴일, 서비스 캘린더와 심야의 날짜 경계를 확인한다.
- 1시간 단위 수요로 15분과 30분 차이를 정밀 검증했다고 주장하지 않는다.
- 탄소 효과의 수단 전환율을 사실처럼 단정하지 않는다.
- 입력 완전성 검사가 실패하면 `no_gap`으로 채우지 않고 `unknown`을 유지한다.
- 단축노선은 후보 경로, 정류장, 정차·회차시간, 배차, 차량 투입과 운행거리의 포함 범위를 설정에 명시한다.
- 배출계수·평균 거리·추가 버스 운행 배출량의 출처가 없으면 탄소 결과를 `unsupported`로 둔다.

## 완료 조건

준비된 입력 범위에서는 현행과 시나리오가 동일한 가정에서 재현되고 테스트가 통과해야 한다. 자료가 차단된 경우 지원되지 않는 결과를 `unsupported`로 기록하고 필요한 입력, 코드·테스트, 차단 사유를 제공하면 제한 완료로 본다.
