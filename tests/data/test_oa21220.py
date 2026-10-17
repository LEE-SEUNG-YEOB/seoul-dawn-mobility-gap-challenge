import json
from pathlib import Path
from scripts.audit_oa21220 import COLS, KEY

OUT=Path('outputs/intermediate/data_audit')

def test_oa21220_september_contract_and_keys():
    a=json.loads((OUT/'OA-21220_audit.json').read_text(encoding='utf-8'))
    s=a['september']
    assert sorted(s['daily_counts'])==[f'202609{d:02d}' for d in range(1,31)]
    assert s['columns']==COLS and s['business_key']==KEY
    assert s['duplicate_key_excess']==0 and s['duplicate_rows']==0
    assert not any(s['numeric_invalid_or_negative'].values())
    assert all(s['column_stats'][c]['missing']==0 for c in KEY)
    assert len(a['files'])==5
    assert s['daily_total_vs_observed_hour_sum_mismatch']==19161
    assert s['daily_total_missing_rows']==35474
    assert s['daily_total_matches_observed_hour_sum_rows']+s['daily_total_missing_rows']+s['daily_total_vs_observed_hour_sum_mismatch']==s['row_count']
    assert 'blanket zero inference fails' in s['blank_hour_semantics']

def test_oa21220_scope_does_not_enable_full_join():
    c=json.loads(Path('data/metadata/analysis_contract.json').read_text(encoding='utf-8'))
    d=next(d for d in c['datasets'] if d['dataset_id']=='OA-21220')
    assert 'limited direct-service screening' in d['allowed_uses'][0]
    r=json.loads((OUT/'readiness.json').read_text(encoding='utf-8'))
    assert r['join_ready'] is False and r['mode']=='separate_only'
    assert 'beneficiaries' in r['unavailable_outputs']

def test_archive_manifest_has_five_unique_sources_and_hashes():
    m=json.loads((OUT/'OA-21220_download_manifest.json').read_text(encoding='utf-8'))
    assert len(m['records'])==5
    assert len({r['seq'] for r in m['records']})==5
    for r in m['records']:
        assert Path(r['path']).stat().st_size==r['bytes']
        assert len(r['sha256'])==64 and len(r['members'])==1
