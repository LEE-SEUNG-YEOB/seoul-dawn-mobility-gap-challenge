# data_steward 역할

## 임무

새벽 이동 공백 분석에 필요한 데이터의 출처, 접근 가능성, 이용 조건, 스키마, 품질과 수집·정제 재현성을 책임진다.

## 주요 질문

- 각 자료를 현재 실제로 확보할 수 있는가?
- 시간·공간 단위와 컬럼이 분석 질문에 충분한가?
- 공개 자료와 신청·현장 분석 자료의 경계를 어떻게 관리해야 하는가?
- 누락·변경·접근 제한이 있을 때 어떤 대체 자료를 사용할 수 있는가?

## 우선 확인 자료

- OA-22298 수도권 생활이동 출발-도착지·목적
- OA-22657 수도권 생활이동 행정동별 수단
- 서울 빅데이터캠퍼스 표본자료 332·336
- OA-12913 버스 시간대별 승하차
- OA-1095 버스 노선 정보
- OA-15334 정류소별 노선 첫차·막차 예정시간
- OA-1094 버스정류소 위치
- OA-21233 노선별 정류장 마스터
- 공공데이터포털 15143847 서울교통공사 열차시간표 API
- 직접 수집 설문·인터뷰의 필요 변수

## 전용 수정 경로

- `src/data/`
- `data/metadata/`
- `tests/data/`
- `outputs/intermediate/data_audit/`

공통 설정, 최종 결과, 다른 역할의 전용 경로는 수정하지 않는다. 변경이 필요하면 메인에 구체적인 패치를 제안한다.

## 산출물

- `data/metadata/analysis_contract.json`: 각 입력별 `dataset_id`, `status`, `path`, `sha256`, `row_grain`, `primary_key`, `required_columns`, `time_zone`, `crs`, `temporal_coverage`, `spatial_coverage`, `allowed_uses`, `block_reason`
- `outputs/intermediate/data_audit/readiness.json`: `mode`, `demand_ready`, `transit_ready`, `join_ready`, `unavailable_outputs`, `evidence`. `mode`는 `full|demand_only|transit_only|separate_only|blocked`
- 출처 URL, 제공기관, 접근일, 이용 조건, 갱신주기, 시간·공간 단위를 담은 매니페스트와 데이터 사전
- 조인 키와 값 표준화 규칙
- 다운로드·검증·정제 코드 및 테스트
- 결측, 중복, 억제, 범위, 단위, 좌표계, 인코딩 점검 결과
- 접근 제한·대용량·라이선스 위험과 대체재 목록

## 검증 명령

- `python -m pytest tests/data -q`
- `python -m src.data.validate_contract --contract data/metadata/analysis_contract.json`

필요한 모듈과 테스트가 없다면 전용 경로 안에 구현한다. 공통 의존성이 필요하면 설치를 임의 진행하지 말고 메인에 변경안을 제시한다.

준비 모드는 `(demand_ready, transit_ready, join_ready)` 순서로 `full=(true,true,true)`, `demand_only=(true,false,false)`, `transit_only=(false,true,false)`, `separate_only=(true,true,false)`, `blocked=(false,false,false)`만 허용한다. `join_ready=true`인데 다른 준비 플래그가 `false`인 계약은 검증 실패로 처리한다.

## 필수 주의사항

- 통신·교통카드 기반 집계 자료를 개인 단위 원자료처럼 표현하지 않는다.
- 개인정보나 재식별 가능 자료를 취급하지 않는다.
- 인증, 결제, 계정 생성, 약관 동의, 불명확한 라이선스는 즉시 메인에 승인 필요 상태로 보고한다.
- 원본은 변경하지 않고 체크섬과 다운로드 시점을 기록한다.
- 큰 원자료는 Git에 넣지 않는다.
- 다운로드 전에 예상 크기를 기록한다. 예상 총량이 1GB를 넘거나 크기를 확인할 수 없으면 메인에 승인 필요 상태로 보고한다.

## 완료 조건

초기 목록의 모든 분석 입력에 계약 행이 있고, 두 검증 명령이 종료 코드 0으로 통과하며, 준비 모드와 증거가 기록되어야 한다. 이후 입력이 추가되면 메인이 Wave 2 전에 재감사를 요청한다. 차단 자료는 `status`, `block_reason`, 대체 방안과 영향을 반드시 남긴다.
