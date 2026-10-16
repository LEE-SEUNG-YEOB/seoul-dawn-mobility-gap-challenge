"""Supplement completed file audits with exact mobility business-key checks."""
from pathlib import Path
import json
import duckdb
from src.data.audit import OUT, dump, q

def check_keys(p):
    con=duckdb.connect()
    con.execute("SET memory_limit='4GB'")
    con.execute('SET threads=4')
    con.execute("SET temp_directory='outputs/intermediate/data_audit/key_temp'")
    con.read_csv(str(p),all_varchar=True,header=True,strict_mode=True).create_view('t')
    columns=[x[0] for x in con.execute('DESCRIBE t').fetchall()]
    keys=[c for c in columns if c not in ['cnt','move_dist','move_time','total_cnt'] and not c.endswith('_cnt')]
    grouped=','.join(q(x) for x in keys)
    result=con.execute(f'SELECT coalesce(sum(n-1),0), count(*) FROM (SELECT count(*) n FROM t GROUP BY {grouped} HAVING count(*)>1)').fetchone()
    con.close()
    return {'columns':keys,'duplicate_excess_rows':result[0],'duplicate_groups':result[1],'method':'exact GROUP BY every observed non-measure dimension per file; etl_ymd included'}

def main():
    for p in sorted((OUT/'files').glob('*.json')):
        a=json.loads(p.read_text(encoding='utf-8'))
        if a['dataset_id'] not in ['OA-22300','OA-22657','OA-22298'] or 'business_key_check' in a: continue
        print(a['path'],flush=True)
        a['business_key_check']=check_keys(Path(a['path']))
        dump(p,a)
    print('Available cached mobility business keys audited; run again after full file audit completes.',flush=True)

if __name__=='__main__': main()
