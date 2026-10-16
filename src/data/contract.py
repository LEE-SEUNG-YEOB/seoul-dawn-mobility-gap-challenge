"""Build evidence-based limited-mode contracts from completed local audits."""
from pathlib import Path
import hashlib
import json
from collections import defaultdict
import xml.etree.ElementTree as ET
from src.data.audit import OUT, dump, json_rows

MISSING=['OA-1094','campus-332','campus-336','survey-interview']
SOURCE_URLS={
    'OA-22298':'https://data.seoul.go.kr/dataList/OA-22298/F/1/datasetView.do',
    'OA-22657':'https://data.seoul.go.kr/dataList/OA-22657/F/1/datasetView.do',
    'OA-12913':'https://data.seoul.go.kr/dataList/OA-12913/F/1/datasetView.do',
    'OA-1095':'https://data.seoul.go.kr/dataList/OA-1095/A/1/datasetView.do',
    'OA-15334':'https://data.seoul.go.kr/dataList/OA-15334/F/1/datasetView.do',
    'OA-21233':'https://data.seoul.go.kr/dataList/OA-21233/S/1/datasetView.do',
    'data-go-15143847':'https://www.data.go.kr/data/15143847/openapi.do'}

def first_bus_evidence():
    counts=defaultdict(int); pairset=set()
    for p in Path('data/raw/bus/OA-15334').rglob('*.jsonl'):
        for line in p.read_text(encoding='utf-8').splitlines():
            row=json.loads(line); counts['responses']+=1
            try: root=ET.fromstring(row.get('raw_xml',''))
            except ET.ParseError:
                counts['invalid_xml']+=1; continue
            for item in root.findall('.//itemList'):
                t=item.findtext('firstBusTm',''); ars=item.findtext('arsId','')
                valid=len(t)==6 and t.isdigit() and int(t[:2])<24 and int(t[2:4])<60 and int(t[4:])<60
                counts['valid_first_time_items']+=int(valid)
                counts['invalid_first_time_items']+=int(not valid)
                if valid and ars not in ['', '0', '00000']:
                    pairset.add((ars,item.findtext('busRouteId','')))
    counts['valid_nonzero_ars_route_pairs']=len(pairset)
    stations={}
    for p in Path('data/raw/bus/OA-21231').rglob('page_*.json'):
        for row in json_rows(json.loads(p.read_text(encoding='utf-8'))):
            ars=str(row.get('CRTR_NO',''))
            if len(ars)==5 and ars not in ['00000']:
                stations[str(row['CRTR_ID'])]=ars
    universe=set()
    for p in Path('data/raw/bus/OA-21233').rglob('page_*.json'):
        for row in json_rows(json.loads(p.read_text(encoding='utf-8'))):
            ars=stations.get(str(row.get('CRTR_ID','')))
            if ars and row.get('RTE_ID'):
                universe.add((ars,str(row['RTE_ID'])))
    counts['reconstructed_request_universe']=len(universe)
    counts['valid_pairs_matched_to_request_universe']=len(pairset & universe)
    counts['valid_pairs_outside_request_universe']=len(pairset - universe)
    return dict(counts)
UNSUPPORTED=['citywide_service_gap_ranking','citywide_route_priority','beneficiaries','vehicle_hour_benefit','carbon_effect','15_vs_30_minute_precise_effect','short_route_effect','before_after_reachable_area','bus_weekday_weekend_comparison']

def build_contract(reports):
    groups=defaultdict(list)
    for r in reports: groups[r['dataset_id']].append(r)
    entries=[]
    for ds,rs in sorted(groups.items()):
        mobility=ds in ['OA-22300','OA-22657','OA-22298']
        tabular=[r for r in rs if r.get('row_count',0)>0]
        columns=sorted(set(c for r in tabular for c in r.get('columns',[])))
        dates=sorted(set(d for r in rs for d in r.get('code_counts',{}).get('etl_ymd',{})))
        if mobility: coverage={'start':dates[0] if dates else None,'end':dates[-1] if dates else None,'observed_days':dates,'time_resolution':'hourly except commute peaks 20 minute; dawn hourly'}
        elif ds=='OA-12913': coverage={'month':'202609','time_resolution':'monthly totals by hour; no daily or weekday axis'}
        elif ds in ['OA-1095','OA-15067']: coverage={'snapshot':'2026-09-02','validity_for_all_September':'not_verified'}
        elif ds.startswith('OA-') or ds=='data-go-15143847': coverage={'snapshot':'2026-10-16','historical_September_validity':'not_verified'}
        else: coverage={'validity':'mixed_vintages; inspect filenames and file audit','latest_mobility_codebook':'202608' if ds=='mobility_codebooks' else None}
        limits=[]
        if ds=='OA-15334': limits=['Nonprobability subset: completed 1999/44735 requests; missing pairs unknown; successful valid timetable pairs require XML audit; one response outside current pair set.']
        if ds=='data-go-15143847': limits=['Snapshot 2026-10-16, requested search_date 2026-09-15T04:30:00; no proof of historical validity for every September service day; empty categories are unknown, not absence of service.']
        if mobility: limits=['KT estimated aggregate movement counts, not unique persons or observed unmet demand; suppressed/unpublished cells unknown; no expansion/imputation.']
        if ds=='data-go-15129688': limits=['SGIS ADM_CD differs from mobility ADMI_CD. Never join code equality. Boundary vintage differs; ambiguous split neighborhoods unknown.']
        if ds=='OA-12913': limits=['T-money monthly aggregate; cannot compare weekdays/weekends or infer unmet demand.']
        grain='source aggregate record'
        if ds in ['OA-22300','OA-22657']: grain='date × origin × destination × departure bin × arrival bin × nationality group × purpose or mode; mean distance/time fields; provider uniqueness not guaranteed'
        if ds=='OA-22298': grain='date × destination × time bin × purpose; domestic age-sex aggregate'
        if ds=='OA-12913': grain='month × route × stop × hour (wide columns)'
        uses=['independent descriptive audit']
        if mobility or ds=='OA-12913': uses+=['demand candidates only; no service gap inference']
        if ds in ['OA-15334','OA-1095','OA-15067','OA-21230','OA-21231','OA-21232','OA-21233','data-go-15143847']: uses+=['limited snapshot supply inventory and observed timetable cases only']
        manifest=[r['source_manifest'] for r in rs if 'source_manifest' in r]
        entries.append({'dataset_id':ds,'status':'available_limited','path':[r['path'] for r in rs], 'sha256':{r['path']:r['sha256'] for r in rs},'row_grain':grain,'primary_key':['source_path','source_row_number'],'primary_key_note':'Generated physical key; natural key must not be assumed unique. Exact full-row duplicates measured per file; no silent deduplication.','required_columns':columns,'time_zone':'Asia/Seoul','crs':'See per-file .prj; coordinate tables longitude/latitude degrees, CRS not independently certified' if ds in ['data-go-15129688','OA-1095','OA-15067','OA-21231','OA-21232'] else None,'temporal_coverage':coverage,'spatial_coverage':'Seoul administrative dong; outside Seoul coarser codes' if mobility else 'source-specific; not all Seoul service guaranteed','allowed_uses':uses,'block_reason':limits,'file_count':len(rs),'row_count':sum(r.get('row_count',0) for r in tabular),'bytes':sum(r['bytes'] for r in rs),'source_url':SOURCE_URLS.get(ds),'provider':'Seoul / KT' if mobility else 'See local source manifest and reference documents','access_date':next((m.get('retrieved_at') for m in manifest if m.get('retrieved_at')),None),'access_evidence':'Existing local files only; no network access during analysis','license':'Public-source usage stated in local context; exact license version not independently verified, do not redistribute raw data','refresh_frequency':'unknown unless local source manifest states otherwise','source_manifests':manifest})
    for ds in MISSING:
        entries.append({'dataset_id':ds,'status':'unavailable','path':[],'sha256':{},'row_grain':'unknown','primary_key':[],'required_columns':[],'time_zone':'Asia/Seoul','crs':None,'temporal_coverage':None,'spatial_coverage':None,'allowed_uses':[],'block_reason':['Not present locally; new collection prohibited'],'alternative':'OA-15067 and OA-21231 for station location' if ds=='OA-1094' else 'Remain unsupported; later authorized collection/validation required'})
    demand_files=groups.get('OA-22300',[])
    days=sorted(set(d for r in demand_files for d in r.get('code_counts',{}).get('etl_ymd',{})))
    required={'o_admdong_cd','d_admdong_cd','st_time_cd','fns_time_cd','cnt','etl_ymd','move_purpose'}
    demand_ready=len(days)==30 and days[0]=='20260901' and days[-1]=='20260930' and all(required<=set(r['columns']) and all(r['column_stats'][c]['missing']==0 for c in required) and r.get('numeric_checks',{}).get('cnt',{}).get('invalid',1)==0 and r.get('numeric_checks',{}).get('cnt',{}).get('negative',1)==0 for r in demand_files)
    first_bus=first_bus_evidence()
    transit_ready=first_bus.get('valid_nonzero_ars_route_pairs',0)>0 and all(sum(r.get('row_count',0) for r in groups.get(d,[]))>0 for d in ['OA-1095','OA-15067','data-go-15143847'])
    mode='separate_only' if demand_ready and transit_ready else 'demand_only' if demand_ready else 'transit_only' if transit_ready else 'blocked'
    readiness={'mode':mode,'demand_ready':demand_ready,'transit_ready':transit_ready,'join_ready':False,'transit_ready_scope':'technical inventory and partial timetable cases only, not historical citywide accessibility','unavailable_outputs':UNSUPPORTED,'evidence':{'file_audit':'outputs/intermediate/data_audit/file_audit.json','audited_files':len(reports),'first_bus_xml_audit':first_bus,'demand_days':days,'OA-15334_completed_requests':1999,'OA-15334_request_universe':44735,'OA-15334_coverage_percent':1999/44735*100,'sampling':'nonprobability; missing is unknown','temporal_mismatch':'October supply snapshot versus September demand; no complete service calendar/walking/transfer inputs','no_join_reason':'Incomplete nonprobability first-bus coverage and temporal/service-calendar gaps'}}
    contract={'schema_version':1,'analysis_period':{'start':'2026-09-01','end':'2026-09-30','hours':[3,4,5],'time_zone':'Asia/Seoul'},'datasets':entries,'readiness_path':'outputs/intermediate/data_audit/readiness.json','rules':{'time_bin':'03:00 inclusive to 06:00 exclusive; HH and HHMM are mixed, never zero-pad HH into HHMM','geography':'Mobility ADMI_CD and SGIS ADM_CD are distinct code systems; validated crosswalk only; splits unknown','ids':'Read identifiers as strings; preserve leading zeros; do not match ARS ID 0','missing':'unknown; never zero or no_gap','duplicate':'Exact full-row counts available per file; aggregate records are not persons; natural-key duplicates require explicit handling','raw_data':'read-only; no downloads or authenticated API calls','separate_axes':'Do not add purpose and mode counts; do not infer demand-weighted supply effects'}}
    dump('data/metadata/analysis_contract.json',contract)
    dump(OUT/'analysis_contract.json',contract)
    dump(OUT/'readiness.json',readiness)
    dump(OUT/'data_dictionary.json',{'units':{'cnt':'estimated movements, not distinct persons','total_cnt':'estimated movements','move_dist':'mean meters','move_time':'mean minutes','bus_boarding':'monthly recorded boardings'},'purpose_codes':{'1':'출근','2':'등교','3':'귀가','4':'쇼핑','5':'관광','6':'병원','7':'기타'},'mode_codes':{'1':'항공','2':'기차','3':'고속버스','4':'광역버스','5':'일반버스','6':'지하철','7':'도보','8':'차량','9':'기타'},'evidence':'data/reference/mobility_codebooks/*레이아웃.xlsx','files':[{'path':r['path'],'columns':r.get('columns',[]),'sheets':list(r.get('sheets',{}))} for r in reports]})
    dump(OUT/'lineage.json',{'command':'python -m src.data.audit','inputs':[{'path':r['path'],'sha256':r['sha256'],'bytes':r['bytes']} for r in reports],'outputs':['file_audit.json','analysis_contract.json','readiness.json','data_dictionary.json'],'network_used':False,'raw_mutated':False})
