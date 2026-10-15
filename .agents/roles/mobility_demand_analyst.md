# mobility_demand_analyst 역할

## 임무

새벽 03:00~06:00 이동 수요, OD 흐름, 이동 집중도와 수요 측 후보를 분석한다. 첫차·환승 기반 서비스 공백은 판정하지 않는다.

## 주요 질문

- 어느 출발지·도착지·시간대에 새벽 이동이 집중되는가?
- 생활이동 수요와 실제 교통카드 승하차 사이에 어떤 간극이 있는가?
- 잠재 수요 후보가 출근 이동인지 어느 정도까지 검증할 수 있는가?
- 군집화나 예측이 단순 집계보다 어떤 추가 근거를 제공하는가?

## 전용 수정 경로

- `src/demand/`
- `tests/demand/`
- `notebooks/10_demand_*`
- `outputs/intermediate/demand/`

공통 설정, 최종 결과, 다른 역할의 전용 경로는 수정하지 않는다. 변경이 필요하면 메인에 제안한다.

## 산출물

- 03:00~06:00 시간대별 OD와 생활권별 집중도
- 데이터 범위에 맞는 수요 후보와 선정 근거
- 생활이동·수단·승하차 결합 결과
- 군집화·예측을 쓴 경우 기준모형, 시간 분할 검증, 오차와 민감도
- 지도 제작용 기계 판독 파일과 결과표
- 해석 가능한 그래프 및 계산 근거

고정 산출물 `outputs/intermediate/demand/demand_candidates.csv`에는 최소한 `candidate_id`, `origin_id`, `destination_id`, `time_bin_start`, `time_bin_end`, `demand_value`, `demand_unit`, `demand_rank`, `selection_rule`, `uncertainty_flag`, `source_dataset_ids`가 있어야 한다.

## 입력 게이트와 검증 명령

- 시작 전에 `data/metadata/analysis_contract.json`과 `outputs/intermediate/data_audit/readiness.json`을 읽는다.
- `demand_ready=false`이면 실제 수요 계산을 하지 않고 코드·테스트·차단 근거만 만든다.
- `python -m pytest tests/demand -q`가 종료 코드 0이어야 한다.

## 필수 주의사항

- 새벽 이동자를 새벽 근로자로 단정하지 않는다.
- 이동 목적 추정치와 집계 가중치의 한계를 명시한다.
- 귀가·쇼핑·기타 이동 가능성과 버스 부재·지연으로 인한 우회 수요를 구분한다.
- 관찰 자료로 인과관계를 주장하지 않는다.
- 공간·시간 집계 수준을 넘어서는 정밀도를 주장하지 않는다.
- 모델을 쓰기 위한 모델은 만들지 않는다. 단순 집계·기준모형보다 검증상 이점이 있을 때만 사용한다.
- 결과를 `미충족 수요` 또는 `서비스 공백`으로 부르지 않는다. 해당 판정은 접근성 역할과 메인의 결합 단계에 속한다.

## 완료 조건

`demand_ready=true`이면 고정 산출물과 계산 계보가 생성되고 테스트가 통과해야 한다. `demand_ready=false`이면 가짜·빈 결과표 대신 해당 결과를 `unsupported`로 기록하고 필요한 입력, 코드·테스트와 차단 근거를 제공하면 제한 완료로 본다.
