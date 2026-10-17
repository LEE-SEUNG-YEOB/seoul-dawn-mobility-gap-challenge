# 새벽 이동 공백 데이터 분석

이 저장소는 서울의 새벽 03:00~06:00 이동 공백과 첫차 조정·새벽 단축노선 시나리오를 분석하기 위한 작업 공간이다.

범위는 **데이터 분석만**이다. 공모전 분석 기획서, 참가신청서, 정책 제안서와 발표 원고는 이 저장소에서 작성하지 않는다. 분석 결과는 다른 팀원이 기획서를 작성할 수 있도록 코드, 표, 지도, 그림, 가정, 한계와 재현 절차 형태로 전달한다.

## 분석 완료 상태

분석은 `COMPLETE_LIMITED` 상태로 완료되었다. 2026년 9월 서울 내부 이동을 기준으로 수요 분석과 대중교통 공급자료 점검을 각각 완료했으며, 최종 검증 상태는 `separate_only`다.

- 수요 분석: 사용 가능 (`demand_ready=true`)
- 대중교통 공급자료 점검: 사용 가능 (`transit_ready=true`)
- 상위 수요 OD 직결 서비스 존재 스크리닝: 제한적 사용 가능
- 수요·공급 결합 및 서비스 공백 판정: 사용 불가 (`join_ready=false`)
- 자동 테스트: 39개 통과
- 독립 QA: 치명적·중요 오류 0건

따라서 아래 결과는 **새벽 이동수요와 버스 이용 현황을 보여 주는 기초 분석**으로 사용할 수 있다. 현재 자료만으로 서울 전역의 서비스 공백이나 우선 조정 노선을 확정할 수는 없다.

## 핵심 분석 결과

### 새벽 이동수요

- 생활이동 목적 자료(`OA-22300`)에서 2026년 9월 서울 내부 03:00~06:00 추정 이동량은 **18,196,606.52건**이다.
- 평일(월~금) 일평균은 주말(토~일)보다 03시 **10.71%**, 04시 **10.83%**, 05시 **44.90%** 많았다. 05시에 평일과 주말의 차이가 가장 컸다.
- 출발지 집중도 1위는 03~05시 모두 **마포구 서교동**이었다.
- 도착지 집중도 1위는 03시 **강남구 역삼1동**, 04~05시 **영등포구 여의동**이었다.
- 이동목적 1위는 03시 **귀가 44.93%**, 04시 **기타 53.99%**, 05시 **기타 56.24%**였다.
- 별도 이동수단 자료(`OA-22657`)에서는 도보 비중이 03시 **52.75%**, 04시 **41.19%**, 05시 **29.81%**로 각 시간대에서 가장 높았다.

행정동이 서로 다른 OD 가운데 추정 이동량 상위 수요 후보는 다음과 같다. 이 순위는 서비스 공백 순위가 아니라 **수요 측 검토 후보**다.

| 순위 | 시간 | 출발지 → 도착지 | 추정 이동량 |
|---:|---:|---|---:|
| 1 | 05시 | 강서구 등촌3동 → 강서구 공항동 | 6,528.73 |
| 2 | 05시 | 중랑구 신내1동 → 중랑구 망우본동 | 4,996.02 |
| 3 | 03시 | 마포구 서교동 → 마포구 서강동 | 4,478.51 |

### 버스 이용과 공급자료

- 버스 시간대별 승하차 자료(`OA-12913`)의 03~05시 월간 합계는 승차 **3,085,981건**, 하차 **2,571,832건**이다.
- 시간대별 승차 상위 정류소는 03시 **동대문역·흥인지문**, 04시 **수유역·강북구청**, 05시 **구로디지털단지역**이었다.
- 시간대별 승차 상위 노선은 03시 **N61**, 04시 **152**, 05시 **130**이었다.
- 공급자료 목록에는 버스 노선–정류소 41,688행, 지하철역 11,497행, 버스 노선–노드 88,729행, 지하철 시간표 296,720행이 포함된다.
- 첫차 정보 `OA-15334`는 전체 44,735개 정류소–노선 쌍 중 1,999개만 요청 완료되어 확보율이 **4.4685%**다. 유효한 최초 운행시각 쌍은 1,947개이며 03~06시 사례는 1,041개다. 비확률 확보분이므로 미확보 쌍은 운행 없음이 아니라 `unknown`으로 취급한다.

### 실제 운행 기반 직결 서비스 스크리닝

`OA-21220`의 2026년 9월 노선–정류소–시간별 실제 운행횟수 2,638,894행을 추가해 상위 100개 OD-hour 후보를 확인했다. 같은 노선이 출발지 쪽 정류소를 먼저 지나고 목적지 쪽 정류소를 나중에 지나며, 출발 시간대에 양수 운행횟수가 관측된 경우만 직결 서비스 존재 증거로 분류했다.

- 행정동 경계 내부 정류소 기준: **94개 후보**에서 양수 직결 운행증거 확인
- 행정동 경계 500m 완충 기준: **100개 후보 모두** 확인
- 내부에서는 확인되지 않고 500m 완충 후 확인된 후보: **6개**
- 500m 기준에서도 확인되지 않은 후보: **0개**

따라서 상위 수요 후보만으로는 “직결 노선이 없는 지역”이라는 공백 가설이 지지되지 않았다. 후속 검증은 노선 존재 여부보다 정확한 첫 도착시각, 배차간격, 혼잡·좌석, 목적지 도착 마감에 초점을 둘 필요가 있다.

이 결과는 서비스가 충분하다는 뜻도 아니다. 500m는 개인 보행거리 판정이 아니며, 시간 단위 양수 운행횟수는 동일 차량의 목적지 도착이나 제시간 도착을 보장하지 않는다. `OA-21220` 빈 시간 셀도 무운행이 아니라 `unknown`이다.

주요 결과의 정확한 값은 [분석 인계 문서](reports/analysis_handoff.md), 계산에 사용한 표는 [최종 표 폴더](outputs/final/tables/), 시각화는 [최종 그림 폴더](outputs/final/figures/)에서 확인한다.

## 분석보고서 작성자가 먼저 볼 자료

### 시간이 없으면 이 세 파일부터 보기

1. [analysis_handoff.md](reports/analysis_handoff.md): 분석 결과를 문장으로 설명한 **가장 중요한 인계 문서**다. 보고서 초안을 쓸 때 이 파일을 먼저 읽는다.
2. [analysis_coverage.md](reports/analysis_coverage.md): 어떤 결론까지 말할 수 있는지를 정리한 **사용 가능 범위표**다. `produced`는 사용 가능한 결과, `unsupported`는 현재 자료로 계산하지 못한 결과다.
3. [outputs/final/figures/](outputs/final/figures/): 보고서에서 바로 참고할 수 있는 **최종 그래프와 지도 9개**가 들어 있다. 그림을 사용하기 전 인계 문서의 해석과 한계를 함께 확인한다.

핵심 수치만 빠르게 확인하려면 [summary.json](outputs/final/summary.json)을 보면 된다. 다만 JSON은 기계 판독용 요약이므로, 숫자의 뜻을 이해하거나 보고서 문장으로 옮길 때는 `analysis_handoff.md`를 기준으로 한다.

### 파일별 해설

#### 1. 결과를 이해하는 문서

| 파일 | 무엇이 들어 있나 | 어떻게 보면 되나 | 보고서에서 쓸 부분 |
|---|---|---|---|
| [analysis_handoff.md](reports/analysis_handoff.md) | 핵심 결과, 주요 수치, 공급자료 확보 상태, 해석 한계 | 위에서 아래로 한 번 읽으면 전체 분석 흐름을 이해할 수 있다. 제한적 직결 서비스 스크리닝과 완전한 공백 판정의 차이를 먼저 확인한다. | 분석 결과 본문과 결과 요약의 기준 문서 |
| [analysis_coverage.md](reports/analysis_coverage.md) | 요청한 분석 항목별 `produced`·`unsupported` 판정 | 쓰려는 결론을 첫 번째 열에서 찾고, 판정과 누락 의존성을 확인한다. | 보고서에 넣을 수 있는 주장과 추가 데이터 과제 구분 |
| [assumptions_and_limits.md](reports/assumptions_and_limits.md) | 시간 범위, 이동량 단위, 평일·주말 정의, 공간 연결과 표본 한계 | 보고서의 데이터 설명과 한계 절을 작성할 때 본다. | 방법론, 각주, 한계, 후속 검증 항목 |
| [qa_review.md](reports/qa_review.md) | 테스트, 원자료 해시, 행 수, 결측·중복, 그림 검수 결과 | 최종 제출 직전에 결과가 검증되었는지 확인한다. | 재현성·품질검증 설명의 근거 |

`analysis_coverage.md`를 읽는 예시는 다음과 같다. `03:00~06:00 시간대별 OD 이동량`은 `produced`이므로 사용할 수 있다. `첫차 조정 대상 노선 순위`는 `unsupported`이므로 현재 결과를 노선 우선순위처럼 쓰면 안 된다.

#### 2. 보고서에 숫자를 옮길 때 보는 표

| 파일 | 핵심 열 | 쉬운 해석 | 사용 예시 |
|---|---|---|---|
| [demand_candidates.csv](outputs/final/tables/demand_candidates.csv) | `origin_name`, `destination_name`, `time_bin_start`, `demand_value`, `demand_rank` | 서로 다른 행정동 사이의 새벽 추정 이동량 상위 100개다. `demand_value`는 월간 추정 이동량이며 사람 수가 아니다. | “05시대 등촌3동→공항동 추정 이동량이 수요 후보 중 가장 컸다.” |
| [hour_day_type.csv](outputs/final/tables/hour_day_type.csv) | `hour`, `day_type`, `daily_average` | 시간대별 월~금과 토~일의 하루 평균을 비교한다. 총합 대신 `daily_average`를 봐야 일수 차이를 제거할 수 있다. | “05시대 월~금 일평균은 토~일보다 44.90% 많았다.” |
| [purpose_composition.csv](outputs/final/tables/purpose_composition.csv) | `hour`, `purpose_label`, `hour_share` | 각 시간대 이동목적의 구성비다. `hour_share`에 100을 곱하면 백분율이다. | “03시대 귀가 목적은 44.93%였다.” |
| [mode_composition.csv](outputs/final/tables/mode_composition.csv) | `hour`, `mode_label`, `hour_share` | 각 시간대 이동수단의 구성비다. 목적 자료와 별도 분류이므로 두 표의 이동량을 합치지 않는다. | “03~05시 모두 도보가 가장 큰 비중을 차지했다.” |
| [bus_demand_candidates.csv](outputs/final/tables/bus_demand_candidates.csv) | `stop_name`, `boardings`, `alightings`, `activity_rank` | 03~05시 승하차 활동 합계가 큰 정류소 상위 100개다. 이용이 많은 곳이며 서비스가 부족한 곳이라는 뜻은 아니다. | “구로디지털단지역은 새벽 버스 이용 활동 상위 후보였다.” |
| [transit_coverage_audit.csv](outputs/final/tables/transit_coverage_audit.csv) | `route_id`, `planned_first_time`, `access_gap_status` | 확보된 일부 정류소–노선의 예정 첫차 사례다. 모든 행의 공백 판정은 `unknown`이다. | 전체 현황이나 순위에 쓰지 않고, 제한된 확보 사례를 설명할 때만 사용 |
| [direct_service_screening.csv](outputs/final/tables/direct_service_screening.csv) | `screening_status`, `inside_confirmed_route_count`, `buffer_500m_confirmed_route_count` | 상위 OD별로 행정동 내부와 500m 완충 기준의 직결 운행 존재 증거를 보여 준다. | “상위 100개 중 내부 94개, 500m 기준 100개에서 양수 운행증거가 확인됐다.” |
| [direct_service_route_evidence.csv](outputs/final/tables/direct_service_route_evidence.csv) | `candidate_id`, `access_scope`, `route_name`, `service_evidence_status` | 후보별로 어떤 노선·정류소순서·시간대 양수 운행을 근거로 삼았는지 보여 준다. | 특정 후보의 확인 근거를 검토할 때 사용하며 노선 우선순위로 정렬하지 않는다. |

CSV를 열었을 때 가장 먼저 볼 열은 순위(`demand_rank` 또는 `activity_rank`), 장소 이름, 시간, 값이다. `uncertainty_flag`와 `selection_rule`에는 각 행의 선정 기준과 주의사항이 적혀 있으므로 인용 전에 함께 확인한다.

#### 3. 그림을 고를 때 보는 파일

| 그림 | 보여 주는 내용 | 해석할 때 주의할 점 |
|---|---|---|
| [hour_day_type.png](outputs/final/figures/hour_day_type.png) | 시간대별 월~금·토~일 일평균 이동량 | 공휴일을 별도로 구분한 업무일 비교가 아니다. |
| [top_od_candidates.png](outputs/final/figures/top_od_candidates.png) | 행정동 간 추정 이동량 상위 OD | 수요가 큰 후보이며 대중교통 공백 순위가 아니다. |
| [purpose_composition.png](outputs/final/figures/purpose_composition.png) | 시간대별 이동목적 구성 | 목적은 통신 기반 추정 분류이며 직업을 뜻하지 않는다. |
| [mode_composition.png](outputs/final/figures/mode_composition.png) | 시간대별 이동수단 구성 | 목적축과 수단축의 총량은 서로 더하거나 빼지 않는다. |
| [top_bus_stops.png](outputs/final/figures/top_bus_stops.png) | 새벽 승하차 활동 상위 정류소 | 월간 이용량이며 평일·주말을 나눌 수 없다. |
| [origin_demand_map.png](outputs/final/figures/origin_demand_map.png) | 행정동별 출발 수요 분포 | 경계 시점 차이가 있는 참고도다. |
| [destination_demand_map.png](outputs/final/figures/destination_demand_map.png) | 행정동별 도착 수요 분포 | 진한 지역은 이동 집중 지역이며 공급 부족을 뜻하지 않는다. |
| [acquired_first_bus_distribution.png](outputs/final/figures/acquired_first_bus_distribution.png) | 확보된 첫차 예정시각 사례의 분포 | 전체의 4.47%인 비확률 확보분이므로 서울 전체 분포로 일반화하지 않는다. |
| [direct_service_screening.png](outputs/final/figures/direct_service_screening.png) | 상위 20개 OD의 행정동 내부·500m 완충 직결 서비스 확인 결과 | 양수 운행 존재 증거이며 정확한 도착 가능성이나 서비스 공백 판정이 아니다. |

지도 편집이나 추가 시각화가 필요하면 [dong_demand.geojson](outputs/final/maps/dong_demand.geojson), [bus_demand_candidates.geojson](outputs/final/maps/bus_demand_candidates.geojson), [direct_service_screening.geojson](outputs/final/maps/direct_service_screening.geojson)을 사용한다. 마지막 파일의 직선은 OD 대표점을 연결한 표시이며 실제 버스 경로가 아니다.

#### 4. 검증과 재현에만 주로 쓰는 파일

- [summary.json](outputs/final/summary.json): 상태, 핵심 합계, 행 수를 한곳에 모은 기계 판독용 요약이다.
- [artifact_manifest.json](outputs/final/artifact_manifest.json): 최종 산출물 목록과 SHA256 해시다. 파일 누락이나 변경 여부를 확인할 때 쓴다.
- [transit_supply_inventory.csv](outputs/final/tables/transit_supply_inventory.csv): 버스 공급 원자료별 행 수와 품질 점검 결과다.
- [subway_timetable_inventory.csv](outputs/final/tables/subway_timetable_inventory.csv): 지하철 시간표의 노선·요일 구분별 보유 현황이다.

이 네 파일은 일반적인 결과 서술보다 수치 확인, 데이터 관리, 재현성 검증에 적합하다.

보고서 본문은 `분석 범위와 데이터 → 시간대별 수요 → 주요 출발·도착지와 OD 후보 → 버스 이용 현황 → 공급자료 확인 결과 → 한계와 추가 검증 과제` 순서로 구성하면 된다. 표나 그림을 사용할 때는 원자료 코드, 분석 기간, 단위, 집계 기준을 함께 적는다.

### 보고서 표현 기준

| 분석 결과 | 사용하기 적절한 표현 | 피해야 할 해석 |
|---|---|---|
| 생활이동량 | 추정 이동량, 추정 통행 | 고유 이용자 수, 근로자 수 |
| OD 상위 순위 | 수요 측 검토 후보 | 서비스 공백 순위, 노선 신설 우선순위 |
| 목적·수단 자료 | 서로 다른 분류축의 별도 결과 | 두 자료의 합산·차감, 동일 모집단으로 단정 |
| 버스 승하차 | 월간 03~05시 이용 활동 | 생활이동량에서 직접 차감 가능한 공급량 |
| `OA-15334` | 확보된 비확률 사례의 첫차 분포 | 서울 전체 첫차 분포, 미확보 쌍의 운행 없음 |
| `OA-21220` 직결 스크리닝 | 출발시간대 양수 직결 운행 존재 증거 | 제시간 도착 보장, 서비스 충분, 서비스 공백 해소 |
| 월~금·토~일 비교 | 달력상 요일유형별 일평균 | 업무일·휴일 효과의 인과 추정 |

현재 결과로는 도시 전체 서비스 공백 순위, 노선 조정 우선순위, 15분·30분 시나리오 효과, 단축노선 효과, 총수혜자, 차량 운행시간당 수혜자, 전후 접근가능 면적, 탄소감축 효과를 제시하지 않는다. 이런 결론에는 정류소별 정확한 출발·도착시각, 완전한 운행일·환승·보행망, 목적지 도착 마감과 더 세밀한 수요자료가 필요하다.

보고서 제출 전에는 다음을 확인한다.

- 모든 핵심 수치가 `outputs/final/tables/` 또는 `outputs/final/summary.json`과 일치하는가
- 후보를 확정적 공백이나 정책 우선순위로 표현하지 않았는가
- 추정 이동량의 단위를 사람 수로 바꾸어 쓰지 않았는가
- 목적과 수단의 총량을 서로 더하거나 빼지 않았는가
- `OA-15334`의 4.4685% 비확률 확보 한계를 본문이나 각주에 명시했는가
- 지도와 그림의 기간·단위·집계 기준을 캡션에 적었는가

## 에이전트로 분석 시작하기

에이전트 실행 설정은 로컬 전용이며 Git에 포함하지 않는다. 새 환경에서 분석을 실행하려면 `AGENTS.md`, `.agents/`, `prompts/`를 별도로 전달받아 저장소 루트에 배치해야 한다.

1. 저장소 루트에서 에이전트를 실행한다.
2. `prompts/RUN_ANALYSIS.md`의 내용을 작업 요청으로 사용한다.
3. 멀티에이전트 기능이 지원되면 프롬프트가 세 전문 역할을 실제 생성하고, 통합 후 독립 QA 역할을 생성하도록 요구한다.

상시 규칙은 `AGENTS.md`, 역할별 상세 지침은 `.agents/roles/`에 있다.

## 핵심 참고자료

다음 원본 참고자료는 로컬 `docs/context/`에 배치해 사용한다. 해당 폴더는 Git에 포함하지 않으므로 새 환경에서는 별도로 전달받아야 한다.

- `docs/context/주제.txt`
- `docs/context/새벽_이동공백_분석_데이터_확보처_하이퍼링크_수정본.docx`
- `docs/context/PROJECT_CONTEXT.md`

## 현재 데이터 확보 상태와 분석 범위

대회 마감 일정을 고려해 수요·이용 현황 분석은 현재 확보된 데이터로 바로 진행한다.

- 생활이동 OD·목적: `OA-22300`
- 이동수단: `OA-22657`
- 버스 시간대별 승하차: `OA-12913`
- 버스 노선–정류소–시간별 실제 운행횟수: `OA-21220`
- 버스 노선·정류소, 행정경계, 지하철 시간표: 로컬 스냅샷 확보. 분석 월 전체의 역사적 유효성과 실제 운행은 미검증

따라서 2026년 9월을 기준으로 새벽 이동수요, 이동목적·수단, 버스 이용량과 대중교통 공급 현황의 기초 분석을 수행할 수 있다.

다만 서울 전역의 정밀한 버스 공급 공백 분석에 필요한 `OA-15334`는 전체 44,735개 정류소–노선 쌍 중 1,999개만 확보되어 있다. 확보율은 약 4.47%이며, API 일일 호출 제한과 대회 마감 일정 때문에 추가 일일 배치를 기다리지 않고 2026-10-16 하루에 확보한 범위로 진행한다.

`OA-15334` 확보분은 확률표본이 아니므로 다음 결과를 서울 전체의 확정적인 결론으로 제시하지 않는다.

- 자치구·행정동별 버스 공급 공백 순위
- 첫차 조정 대상 노선 순위
- 서비스 조정에 따른 전체 수혜 인원
- 서울 전역의 첫차 이전·막차 이후 이동공백 비율

해당 데이터는 확보된 정류소–노선 범위의 참고 분석과 사례 확인에만 사용하고, 전체 지역에 대한 결론에는 자료 한계를 명시한다.

## Git 원칙

분석 코드와 공유 결과는 Git으로 추적한다. `data/`, `docs/context/`, `.agents/`, `prompts/`와 `AGENTS.md`, 대용량 원자료, 캐시, 임시 파일, 인증정보 및 로컬 QA 로그는 `.gitignore`에서 제외한다.

일반 커밋은 분석 진행 중 자유롭게 만들 수 있다. 강제 푸시, 기록 재작성, 프로젝트 밖 접근과 위험 작업은 사전 승인이 필요하다.

## 재현 가능한 분석 실행

현재 검증 상태는 `separate_only`다. 수요 결과와 제한된 공급 목록은 각각 재현되며, 수요·공급 결합 결과는 만들지 않는다. 원자료는 `data/` 아래에서 읽기 전용으로 사용한다.

검증 환경은 Python 3.13.2다. 새 환경에서는 먼저 프로젝트 전용 환경과 고정 의존성을 설치한다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

로컬 원자료와 `data/metadata/analysis_contract.json`을 배치한 뒤 실행 순서는 다음과 같다.

```powershell
.\.venv\Scripts\python.exe -m src.data.validate_contract --contract data/metadata/analysis_contract.json --verify-hashes
.\.venv\Scripts\python.exe scripts/audit_oa21220.py
.\.venv\Scripts\python.exe -m src.demand.run
.\.venv\Scripts\python.exe -m src.demand.direct_service_inputs
.\.venv\Scripts\python.exe -m src.access.build_supply_audit
.\.venv\Scripts\python.exe -m src.access.build_observed_bus_service
.\.venv\Scripts\python.exe -m src.integration.build_direct_service_screen
.\.venv\Scripts\python.exe -m src.reporting.build_report
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.reporting.provenance --write
```

최종 표·지도·그림은 `outputs/final/`, 분석 범위와 인계 내용은 `reports/analysis_coverage.md`와 `reports/analysis_handoff.md`에 있다. OA-15334 미확보 정류소–노선은 0이나 `no_gap`이 아니라 `unknown`이다.
