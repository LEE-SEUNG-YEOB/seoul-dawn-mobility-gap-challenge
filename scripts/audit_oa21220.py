"""Audit local OA-21220, preserving blank hourly values as unknown."""
from pathlib import Path
import json
import sys
import shutil
import csv
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import duckdb
from src.data.audit import dump,sha256

OUT=Path('outputs/intermediate/data_audit')
COLS=['기준_날짜','노선_ID','정류장_ID','버스운행횟수']+[f'버스운행횟수_{h:02d}시' for h in range(24)]+['정류장_순서']
KEY=['기준_날짜','노선_ID','정류장_ID','정류장_순서']
def q(s): return '"'+s+'"'

def audit_table(con):
    cols=[r[0] for r in con.execute('DESCRIBE t').fetchall()]
    if cols!=COLS: raise ValueError('Unexpected OA-21220 columns')
    n=con.execute('SELECT count(*) FROM t').fetchone()[0]
    stats={}
    for c in cols:
        z=con.execute(f'SELECT count(*) FILTER(WHERE {q(c)} IS NULL),min({q(c)}),max({q(c)}) FROM t').fetchone()
        stats[c]=dict(zip(['missing','min','max'],z))
    dup=con.execute('SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) n FROM t GROUP BY '+','.join(map(q,KEY))+' HAVING count(*)>1)').fetchone()[0]
    full_dup=n-con.execute('SELECT count(*) FROM (SELECT DISTINCT * FROM t)').fetchone()[0]
    invalid=con.execute('SELECT '+','.join(f'count(*) FILTER(WHERE {q(c)} IS NOT NULL AND (try_cast({q(c)} AS BIGINT) IS NULL OR try_cast({q(c)} AS BIGINT)<0))' for c in COLS[3:])+' FROM t').fetchone()
    hours=COLS[4:28]
    # Diagnostic sum of observed cells only; does NOT convert blank to semantic zero.
    observed_sum='+'.join(f'coalesce(try_cast({q(c)} AS BIGINT),0)' for c in hours)
    mismatch=con.execute(f'SELECT count(*) FILTER(WHERE try_cast("버스운행횟수" AS BIGINT) != {observed_sum}) FROM t').fetchone()[0]
    dates=dict(con.execute('SELECT "기준_날짜",count(*) FROM t GROUP BY 1 ORDER BY 1').fetchall())
    return {'row_count':n,'columns':cols,'column_stats':stats,'business_key':KEY,'duplicate_key_excess':dup,'duplicate_rows':full_dup,'numeric_invalid_or_negative':dict(zip(COLS[3:],invalid)),'daily_counts':dates,'daily_total_vs_observed_hour_sum_mismatch':mismatch,'daily_total_missing_rows':stats['버스운행횟수']['missing'],'daily_total_matches_observed_hour_sum_rows':n-stats['버스운행횟수']['missing']-mismatch,'hour_columns':list(range(24)),'blank_hour_semantics':'unknown; no official blank=zero definition verified; blanket zero inference fails reconciliation'}

def main():
    stage=OUT/'oa21220_utf8';stage.mkdir(exist_ok=True)
    files=sorted(Path('data/raw/bus/OA-21220/extracted').glob('*.csv'))
    if len(files)!=5: raise ValueError('Five official weekly CSVs required')
    con=duckdb.connect();con.execute("SET memory_limit='2GB'");con.execute('SET threads=4')
    reports=[]
    for p in files:
        target=stage/p.name
        with p.open(encoding='cp949',newline='') as src,target.open('w',encoding='utf-8',newline='') as dst:
            reader=csv.reader(src,strict=True); writer=csv.writer(dst,lineterminator='\n')
            header=next(reader)
            if header!=COLS:raise ValueError('Unexpected original schema')
            writer.writerow(header)
            for row in reader:
                if len(row)!=len(COLS):raise ValueError('Malformed original row')
                writer.writerow(row)
        con.read_csv(str(target),all_varchar=True,header=True,strict_mode=True).create_view('t',replace=True)
        a=audit_table(con)|{'path':p.as_posix(),'dataset_id':'OA-21220','bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha256(p),'encoding':'cp949'}
        reports.append(a);print(p.name,a['row_count'],flush=True)
    con.read_csv([str(stage/p.name) for p in files],all_varchar=True,header=True,strict_mode=True).filter('"기준_날짜" BETWEEN \'20260901\' AND \'20260930\'').create_view('t',replace=True)
    sept=audit_table(con);con.close()
    manifest=json.loads((OUT/'OA-21220_download_manifest.json').read_text(encoding='utf-8'))
    summary={'dataset_id':'OA-21220','status':'available_limited','files':reports,'september':sept,'source_url':manifest['source_url'],'retrieved_at':manifest['retrieved_at'],'license':manifest['license'],'limitations':['Hourly aggregates cannot establish exact first arrival or travel time','Blank hourly cells remain unknown','Route sequence and stop IDs require independently verified joins','Missing rows do not prove absence of service','Actual recorded run counts support limited direct-service screening only; not unmet demand or benefits']}
    dump(OUT/'OA-21220_audit.json',summary)
    paths=[r['path'] for r in manifest['records']]+[r['path'] for r in reports]
    fingerprints={r['path']:r['sha256'] for r in manifest['records']+reports}
    entry={'dataset_id':'OA-21220','status':'available_limited','path':paths,'sha256':fingerprints,'row_grain':'date × route ID × stop ID × stop sequence; total and 24 hourly run-count columns','primary_key':KEY,'required_columns':COLS,'time_zone':'Asia/Seoul','crs':None,'temporal_coverage':{'raw_start':'20260831','raw_end':'20261004','analysis_start':'20260901','analysis_end':'20260930','observed_analysis_dates':sorted(sept['daily_counts']),'time_resolution':'hourly'},'spatial_coverage':'provider route-stop records; complete Seoul spatial coverage not assumed','allowed_uses':['actual recorded run-count based limited direct-service screening','independent date/hour/route/stop supply description; blanks and missing rows unknown'],'block_reason':summary['limitations'],'source_url':manifest['source_url'],'provider':'서울특별시','access_date':manifest['retrieved_at'],'license':manifest['license'],'row_count':sum(r['row_count'] for r in reports),'analysis_row_count':sept['row_count'],'file_count':10,'audit_path':(OUT/'OA-21220_audit.json').as_posix()}
    c=json.loads(Path('data/metadata/analysis_contract.json').read_text(encoding='utf-8'))
    c['datasets']=[d for d in c['datasets'] if d['dataset_id']!='OA-21220']+[entry]
    c['rules']['OA-21220_acquisition']='Explicitly authorized supplementary public unauthenticated acquisition; existing raw inputs unchanged'
    dump('data/metadata/analysis_contract.json',c);dump(OUT/'analysis_contract.json',c)
    readiness=json.loads((OUT/'readiness.json').read_text(encoding='utf-8'))
    readiness['evidence']['OA-21220']={'audit':(OUT/'OA-21220_audit.json').as_posix(),'september_rows':sept['row_count'],'observed_days':len(sept['daily_counts']),'blank_hour_semantics':'unknown','scope':'limited actual-run direct-service screening only'}
    readiness['transit_ready_scope']='technical inventory, partial timetable cases, and limited OA-21220 actual-run direct-service screening; no integrated accessibility inference'
    assert readiness['join_ready'] is False
    dump(OUT/'readiness.json',readiness)
    existing=json.loads((OUT/'file_audit.json').read_text(encoding='utf-8'))
    archive_reports=[{'path':r['path'],'dataset_id':'OA-21220','bytes':r['bytes'],'sha256':r['sha256'],'format':'zip','members':r['members']} for r in manifest['records']]
    all_reports=[r for r in existing if r['dataset_id']!='OA-21220']+archive_reports+reports
    dump(OUT/'file_audit.json',all_reports)
    readiness['evidence']['audited_files']=len(all_reports)
    dump(OUT/'readiness.json',readiness)
    lineage=json.loads((OUT/'lineage.json').read_text(encoding='utf-8'))
    lineage['inputs']=[{'path':r['path'],'sha256':r['sha256'],'bytes':r['bytes']} for r in all_reports]
    lineage['supplementary_command']='python scripts/audit_oa21220.py'
    lineage['supplementary_acquisition_manifest']=(OUT/'OA-21220_download_manifest.json').as_posix()
    lineage['network_used']=True
    lineage['network_scope']='Only expressly authorized OA-21220 public unauthenticated acquisition; prior inputs unchanged'
    dump(OUT/'lineage.json',lineage)
    for target in stage.glob('*.csv'): target.unlink()
    stage.rmdir()

if __name__=='__main__':main()
