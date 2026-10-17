"""Publish reviewed demand and supply results without joining the two axes."""
from pathlib import Path
import json
import shutil

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from shapely.geometry import shape

from src.reporting.geography import load_seoul_geography, write_geojson
from src.reporting.plots import bars, choropleth, save


ROOT = Path('.')
DEMAND = ROOT / 'outputs/intermediate/demand'
ACCESS = ROOT / 'outputs/intermediate/access'
INTEGRATION = ROOT / 'outputs/intermediate/integration'
FINAL = ROOT / 'outputs/final'


def copy_table(source, name=None):
    target = FINAL / 'tables' / (name or source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return target


def grouped_hour_chart(hour):
    pivot = hour.pivot(index='hour', columns='day_type', values='daily_average').reindex(columns=['weekday', 'weekend'])
    fig, ax = plt.subplots(figsize=(9, 6))
    x = np.arange(len(pivot.index)); width = .36
    ax.bar(x-width/2, pivot.weekday, width, label='월~금', color='#216a81')
    ax.bar(x+width/2, pivot.weekend, width, label='토~일', color='#db8a41')
    ax.set_xticks(x, [f'{h:02d}:00~{h+1:02d}:00' for h in pivot.index])
    ax.set_ylabel('하루 평균 추정 이동량 (통행)')
    ax.grid(axis='y', alpha=.18); ax.set_axisbelow(True); ax.legend(frameon=False)
    fig.suptitle('서울 내부 새벽 출발 이동량', x=.08, ha='left', fontsize=16, fontweight='bold')
    fig.text(.08, .03, 'OA-22300 목적축. 달력상 월~금 22일, 토~일 8일. 공휴일 조정 없음. 고유 인원 수가 아님.', fontsize=9)
    fig.subplots_adjust(left=.13, right=.95, bottom=.15, top=.86)
    save(fig, FINAL/'figures/hour_day_type.png')


def composition_chart(df, label_col, title, path):
    top = df.groupby(label_col, as_index=False).estimated_movements.sum().nlargest(6, 'estimated_movements')[label_col]
    plot = df[df[label_col].isin(top)].pivot(index='hour', columns=label_col, values='hour_share').fillna(0)
    fig, ax = plt.subplots(figsize=(10, 6))
    bottom = np.zeros(len(plot))
    for col in plot.columns:
        ax.bar(plot.index.astype(str), plot[col], bottom=bottom, label=col)
        bottom += plot[col].to_numpy()
    ax.set_ylim(0, 1); ax.set_ylabel('시간대 내 구성비'); ax.set_xlabel('출발 시각')
    ax.legend(frameon=False, ncol=3, loc='upper center', bbox_to_anchor=(.5, -.12))
    fig.suptitle(title, x=.08, ha='left', fontsize=16, fontweight='bold')
    fig.text(.08, .02, '통신 기반 추정 분류. 목적축과 수단축은 서로 합산하거나 차감하지 않음.', fontsize=9)
    fig.subplots_adjust(left=.12, right=.95, bottom=.25, top=.87)
    save(fig, path)


def build():
    (FINAL/'figures').mkdir(parents=True, exist_ok=True)
    (FINAL/'maps').mkdir(parents=True, exist_ok=True)
    key_tables = {
        'demand_candidates.csv': DEMAND/'demand_candidates.csv',
        'intrazonal_summary.csv': DEMAND/'intrazonal_summary.csv',
        'hour_day_type.csv': DEMAND/'hour_summary.csv',
        'purpose_composition.csv': DEMAND/'purpose_composition.csv',
        'mode_composition.csv': DEMAND/'mode_composition.csv',
        'origin_concentration.csv': DEMAND/'origin_concentration.csv',
        'destination_concentration.csv': DEMAND/'destination_concentration.csv',
        'bus_demand_candidates.csv': DEMAND/'bus_demand_candidates.csv',
        'bus_hour_summary.csv': DEMAND/'bus_hour_summary.csv',
        'transit_coverage_audit.csv': ACCESS/'transit_coverage_audit.csv',
        'first_bus_time_distribution.csv': ACCESS/'first_bus_time_distribution.csv',
        'transit_supply_inventory.csv': ACCESS/'transit_supply_inventory.csv',
        'subway_timetable_inventory.csv': ACCESS/'subway_timetable_inventory.csv',
        'direct_service_screening.csv': INTEGRATION/'direct_service_screening.csv',
        'direct_service_route_evidence.csv': INTEGRATION/'direct_service_route_evidence.csv',
    }
    for name, source in key_tables.items():
        copy_table(source, name)

    demand = pd.read_csv(DEMAND/'demand_candidates.csv', dtype={'origin_id':str, 'destination_id':str})
    labels = (demand.origin_district_name + ' ' + demand.origin_name.str.split().str[-1] + ' → ' +
              demand.destination_district_name + ' ' + demand.destination_name.str.split().str[-1] +
              ' ' + demand.time_bin_start.str[:2] + '시')
    bars(labels.head(15), demand.demand_value.head(15), '행정동 간 새벽 수요 후보 상위 15개',
         '9월 추정 이동량 합계 (통행)', 'OA-22300 목적축. 서비스 공백·노선 우선순위가 아닌 수요 측 후보.',
         FINAL/'figures/top_od_candidates.png', horizontal=True)

    hour = pd.read_csv(DEMAND/'hour_summary.csv')
    grouped_hour_chart(hour)
    composition_chart(pd.read_csv(DEMAND/'purpose_composition.csv'), 'purpose_label',
                      '새벽 이동 목적 구성', FINAL/'figures/purpose_composition.png')
    composition_chart(pd.read_csv(DEMAND/'mode_composition.csv'), 'mode_label',
                      '새벽 이동 수단 구성', FINAL/'figures/mode_composition.png')

    bus = pd.read_csv(DEMAND/'bus_demand_candidates.csv')
    bars(bus.stop_name.head(15), (bus.boardings+bus.alightings).head(15),
         '새벽 버스 승하차 활동 상위 정류소', '03~05시 월간 승하차 합계 (건)',
         'OA-12913 월합계. 요일 비교와 미충족 수요 해석은 지원하지 않음.',
         FINAL/'figures/top_bus_stops.png', horizontal=True)
    bus_features = []
    for r in bus.itertuples():
        bus_features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[r.longitude,r.latitude]},
                             'properties':{'candidate_id':r.candidate_id,'stop_id':str(r.stop_id),'ars_id':str(r.ars_id),
                                           'stop_name':r.stop_name,'boardings':r.boardings,'alightings':r.alightings,
                                           'activity_rank':int(r.activity_rank),'scope':'demand-side bus activity candidate'}})
    write_geojson(FINAL/'maps/bus_demand_candidates.geojson', bus_features)

    first = pd.read_csv(ACCESS/'first_bus_time_distribution.csv')
    bars(first.hour.map(lambda x:f'{int(x):02d}시'), first.valid_pair_count,
         '확보된 첫차 예정시각 사례 분포', '유효 정류소–노선 쌍 수',
         'OA-15334 유효 1,947쌍 비확률 확보분만 표시. 서울 전체 분포가 아님.',
         FINAL/'figures/acquired_first_bus_distribution.png')

    features, crosswalk, _ = load_seoul_geography(ROOT)
    mapped = pd.read_csv(DEMAND/'map_dong_demand.csv', dtype={'admi_cd':str}).set_index('admi_cd')
    for feature in features:
        mid = feature['properties']['mobility_id']
        if mid and mid in mapped.index:
            row = mapped.loc[mid]
            feature['properties']['origin_estimated_movements'] = float(row.origin_estimated_movements)
            feature['properties']['destination_estimated_movements'] = float(row.destination_estimated_movements)
        else:
            feature['properties']['origin_estimated_movements'] = None
            feature['properties']['destination_estimated_movements'] = None
    write_geojson(FINAL/'maps/dong_demand.geojson', features)
    crosswalk.to_csv(FINAL/'tables/geography_crosswalk_audit.csv', index=False, encoding='utf-8-sig')
    note = ('OA-22300 목적축 9월 합계. 2025Q2 경계와 202608 코드북 이름 연결 참고도. '
            '용신동/신설동/용두동 분할은 unknown.')
    choropleth(features, 'origin_estimated_movements', '새벽 출발 이동량', note, FINAL/'figures/origin_demand_map.png')
    choropleth(features, 'destination_estimated_movements', '새벽 도착 이동량', note, FINAL/'figures/destination_demand_map.png')

    direct = pd.read_csv(INTEGRATION/'direct_service_screening.csv', dtype={'origin_id':str, 'destination_id':str})
    status_color = {
        'inside_service_confirmed': '#216a81',
        'buffer_only_service_confirmed': '#db8a41',
        'service_unconfirmed_within_500m': '#9a9a9a',
    }
    top = direct.head(20).copy().iloc[::-1]
    top_labels = (top.origin_district_name + ' ' + top.origin_name.str.split().str[-1] + ' → ' +
                  top.destination_district_name + ' ' + top.destination_name.str.split().str[-1] +
                  ' ' + top.time_bin_start.str[:2] + '시')
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(top_labels, top.demand_value, color=top.screening_status.map(status_color))
    ax.set_xlabel('9월 추정 이동량 합계 (통행)')
    ax.grid(axis='x', alpha=.18); ax.set_axisbelow(True)
    ax.legend(handles=[
        Patch(color=status_color['inside_service_confirmed'], label='행정동 내부에서 양수 운행 확인'),
        Patch(color=status_color['buffer_only_service_confirmed'], label='500m 완충 적용 후 양수 운행 확인'),
    ], frameon=False, loc='lower right')
    fig.suptitle('상위 OD의 직결 버스 서비스 존재 증거', x=.08, ha='left', fontsize=16, fontweight='bold')
    fig.text(.08, .015, 'OA-21220 출발시간대 양수 운행 + 동일 노선 후속 정류소 순서. 정확한 도착 가능성·서비스 공백 판정이 아님.', fontsize=9)
    fig.subplots_adjust(left=.32, right=.96, bottom=.10, top=.91)
    save(fig, FINAL/'figures/direct_service_screening.png')

    representative = {
        feature['properties']['mobility_id']: shape(feature['geometry']).representative_point()
        for feature in features if feature['properties']['mobility_id']
    }
    direct_features = []
    for row in direct.itertuples():
        origin, destination = representative.get(row.origin_id), representative.get(row.destination_id)
        if origin is None or destination is None:
            continue
        direct_features.append({
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': [[origin.x, origin.y], [destination.x, destination.y]]},
            'properties': {
                'candidate_id': row.candidate_id,
                'demand_rank': int(row.demand_rank),
                'time_bin_start': row.time_bin_start,
                'origin_name': row.origin_name,
                'destination_name': row.destination_name,
                'demand_value': float(row.demand_value),
                'screening_status': row.screening_status,
                'inside_confirmed_route_count': int(row.inside_confirmed_route_count),
                'buffer_500m_confirmed_route_count': int(row.buffer_500m_confirmed_route_count),
                'geometry_note': 'straight representative-point connector; not a bus path',
            },
        })
    write_geojson(FINAL/'maps/direct_service_screening.geojson', direct_features)

    demand_summary = json.loads((DEMAND/'summary.json').read_text(encoding='utf-8'))
    access_summary = json.loads((ACCESS/'access_summary.json').read_text(encoding='utf-8'))
    direct_summary = json.loads((INTEGRATION/'direct_service_screening_summary.json').read_text(encoding='utf-8'))
    summary = {
        'status':'COMPLETE_LIMITED','readiness_mode':'separate_only','join_ready':False,
        'demand':demand_summary,'access':access_summary,'direct_service_screening':direct_summary,
        'integration_rule':'A limited direct-service presence screen joins demand candidates to positive run evidence; full accessibility and service-gap inference remain unsupported.',
        'unknown_rule':'Unacquired OA-15334 pairs and unresolved geography remain unknown.',
        'unsupported':access_summary['unsupported'] + ['bus weekday/weekend comparison','citywide service gap ranking']
    }
    (FINAL/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
