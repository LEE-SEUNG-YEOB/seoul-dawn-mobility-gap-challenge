"""Local-only streaming audit; never writes under data/raw or data/reference.

Run from repository root. Per-file completed reports allow safe resumption.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict

OUT = Path('outputs/intermediate/data_audit')

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temp.replace(path)

def dataset_id(p):
    return next((x for x in p.parts if x.startswith(('OA-', 'data-go-'))), 'mobility_codebooks')

def q(s):
    return '"' + s.replace('"', '""') + '"'

def csv_audit(p):
    import duckdb
    con = duckdb.connect()
    con.execute("SET memory_limit='1GB'")
    con.execute("SET threads=2")
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET temp_directory='outputs/intermediate/data_audit/duckdb_temp'")
    try:
        with p.open(encoding='utf-8-sig') as f:
            f.read(65536)
        encoding = 'utf-8-sig'
    except UnicodeError:
        encoding = 'cp949'
    if encoding == 'cp949':
        with p.open(encoding=encoding, newline='') as f:
            return rows_audit(csv.DictReader(f)) | {'encoding': encoding}
    # all_varchar preserves leading zeros; strict parsing fails malformed records.
    con.read_csv(str(p), all_varchar=True, header=True, strict_mode=True).create_view('t')
    cols = [x[0] for x in con.execute('DESCRIBE t').fetchall()]
    expressions = ['count(*)']
    for c in cols:
        expressions += [f"count(*) FILTER (WHERE {q(c)} IS NULL OR trim({q(c)})='')", f'min({q(c)})', f'max({q(c)})', f'approx_count_distinct({q(c)})']
    codecols = [c for c in cols if c in ['etl_ymd','st_time_cd','fns_time_cd','time_cd','move_purpose','move_trans','in_forn_div_nm','forn_citiz_nm']]
    numericcols = [x for x in cols if x in ['cnt','total_cnt','move_dist','move_time']]
    expressions += [f'histogram({q(c)})' for c in codecols]
    for c in numericcols:
        expressions += [f"count(*) FILTER(WHERE {q(c)} IS NOT NULL AND try_cast({q(c)} AS DOUBLE) IS NULL)", f"count(*) FILTER(WHERE try_cast({q(c)} AS DOUBLE)<0)", f"min(try_cast({q(c)} AS DOUBLE))", f"max(try_cast({q(c)} AS DOUBLE))"]
    r = con.execute('SELECT ' + ','.join(expressions) + ' FROM t').fetchone()
    stats = {c: dict(zip(['missing', 'min', 'max', 'approx_distinct'], r[1+i*4:5+i*4])) for i,c in enumerate(cols)}
    # Exact row equality, spillable and bounded-memory, not a sampled estimate.
    unique_rows = con.execute('SELECT count(*) FROM (SELECT DISTINCT * FROM t)').fetchone()[0]
    offset=1+4*len(cols)
    codes = {c:r[offset+i] for i,c in enumerate(codecols)}
    offset+=len(codecols)
    numeric = {}
    for i,c in enumerate(numericcols):
        z = r[offset+4*i:offset+4*i+4]
        numeric[c] = dict(zip(['invalid','negative','min','max'],z))
    con.close()
    return {'encoding':encoding,'row_count':r[0], 'columns':cols,'column_stats':stats,'duplicate_rows':r[0]-unique_rows,'duplicate_method':'exact distinct full row per file','code_counts':codes,'numeric_checks':numeric}

def rows_audit(rows):
    n=0; columns=[]; stats={}; seen=set(); duplicates=0
    codes=defaultdict(Counter)
    for row in rows:
        n+=1
        for k,v in row.items():
            if k not in stats:
                columns.append(k); stats[k]={'missing':0,'min':None,'max':None}
            if v is None or str(v).strip()=='': stats[k]['missing']+=1
            else:
                v=str(v)
                stats[k]['min']=min(v,stats[k]['min']) if stats[k]['min'] is not None else v
                stats[k]['max']=max(v,stats[k]['max']) if stats[k]['max'] is not None else v
            if k in ['status_code','error','wknd','updn','CRTR_TYPE','RTE_TYPE','사용년월']:
                codes[k][str(v)]+=1
        key=json.dumps(row,sort_keys=True,ensure_ascii=False,default=str)
        duplicates+=key in seen; seen.add(key)
    return {'row_count':n,'columns':columns,'column_stats':stats,'duplicate_rows':duplicates,'duplicate_method':'exact serialized full row per file','code_counts':dict(codes)}

def json_rows(obj):
    if isinstance(obj,dict):
        if 'response' in obj:
            x=obj['response'].get('body',{}).get('items',{})
            return x.get('item',[]) if isinstance(x,dict) else []
        for val in obj.values():
            if isinstance(val,dict) and 'row' in val: return val['row']
    return []

def audit_file(p):
    result={'path':p.as_posix(),'dataset_id':dataset_id(p),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns,'sha256':sha256(p)}
    if p.suffix=='.csv': result.update(csv_audit(p))
    elif p.suffix=='.jsonl':
        with p.open(encoding='utf-8') as f: result.update(rows_audit(json.loads(x) for x in f if x.strip()))
        result['encoding']='utf-8'
    elif p.suffix=='.json':
        obj=json.loads(p.read_text(encoding='utf-8-sig'))
        result.update(rows_audit(json_rows(obj))); result['encoding']='utf-8'
        if p.name=='manifest.json': result['source_manifest']=obj
    elif p.suffix=='.xlsx':
        import openpyxl
        w=openpyxl.load_workbook(p,read_only=True,data_only=True)
        result['sheets']={}
        for s in w:
            it=iter(s.values); header=next(it,[])
            names=[str(v) if v is not None else f'column_{i}' for i,v in enumerate(header)]
            result['sheets'][s.title]=rows_audit(dict(zip(names,row)) for row in it)
        result['row_count']=sum(x['row_count'] for x in result['sheets'].values())
        result['columns']=next(iter(result['sheets'].values()),{}).get('columns',[])
    elif p.suffix=='.shp':
        import shapefile
        with shapefile.Reader(str(p),encoding='utf-8') as r:
            result['row_count']=len(r); result['columns']=[x[0] for x in r.fields[1:]]; result['bbox']=r.bbox
    elif p.suffix in ['.prj','.cpg']:
        result['text']=p.read_text(encoding='utf-8-sig')
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--refresh',action='store_true'); args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    files=sorted(p for root in ['data/raw','data/reference'] for p in Path(root).rglob('*') if p.is_file())
    reports=[]
    for i,p in enumerate(files):
        cache=OUT/'files'/(hashlib.sha256(p.as_posix().encode()).hexdigest()[:20]+'.json')
        if cache.exists() and not args.refresh:
            a=json.loads(cache.read_text(encoding='utf-8'))
            if a['bytes']!=p.stat().st_size or (a.get('mtime_ns') is not None and a['mtime_ns']!=p.stat().st_mtime_ns): raise ValueError('Input changed; use --refresh: '+str(p))
            if 'mtime_ns' not in a:
                if sha256(p)!=a['sha256']: raise ValueError('Input changed: '+str(p))
                a['mtime_ns']=p.stat().st_mtime_ns; dump(cache,a)
        else:
            print(f'[{i+1}/{len(files)}] {p}',flush=True)
            a=audit_file(p); dump(cache,a)
        reports.append(a)
    dump(OUT/'file_audit.json',reports)
    from src.data.contract import build_contract
    build_contract(reports)
    print('Audit complete',flush=True)

if __name__=='__main__': main()
