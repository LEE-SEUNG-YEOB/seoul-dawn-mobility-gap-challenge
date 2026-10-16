import copy
import json
from pathlib import Path
import pytest
import uuid
from src.data.audit import csv_audit, rows_audit
from src.data.validate_contract import validate

def test_real_contract():
    c=json.loads(Path('data/metadata/analysis_contract.json').read_text(encoding='utf-8'))
    r=json.loads(Path(c['readiness_path']).read_text(encoding='utf-8'))
    assert validate(c,r)

@pytest.mark.parametrize('mode,flags',[('full',(True,True,True)),('demand_only',(False,False,False)),('separate_only',(True,True,True))])
def test_invalid_or_disallowed_mode(mode,flags):
    r={'mode':mode,**dict(zip(['demand_ready','transit_ready','join_ready'],flags))}
    with pytest.raises(AssertionError): validate({'datasets':[]},r)

def test_csv_audit_preserves_codes_and_detects_quality():
    tmp_path=Path('outputs/intermediate/data_audit')/('unit_'+uuid.uuid4().hex)
    tmp_path.mkdir(parents=True)
    p=tmp_path/'sample.csv'
    p.write_text('st_time_cd,cnt,etl_ymd\n03,2.5,20260901\n03,2.5,20260901\n0820,-1,20260901\n04,bad,20260901\n05,,20260901\n',encoding='utf-8')
    r=csv_audit(p)
    assert r['row_count']==5 and r['duplicate_rows']==1
    assert r['code_counts']['st_time_cd']=={'03':2,'04':1,'05':1,'0820':1}
    assert r['numeric_checks']['cnt']['invalid']==1
    assert r['numeric_checks']['cnt']['negative']==1
    assert r['column_stats']['cnt']['missing']==1
    p.unlink()
    tmp_path.rmdir()

def test_rows_missing_and_duplicates():
    r=rows_audit([{'x':None},{'x':None},{'x':'0'}])
    assert r['column_stats']['x']['missing']==2
    assert r['duplicate_rows']==1

def test_completed_mobility_business_key_audit():
    reports=json.loads(Path('outputs/intermediate/data_audit/file_audit.json').read_text(encoding='utf-8'))
    for ds in ['OA-22300','OA-22657','OA-22298']:
        rows=[r for r in reports if r['dataset_id']==ds]
        assert len(rows)==30
        assert all('business_key_check' in r for r in rows)
        assert all(r['business_key_check']['duplicate_excess_rows']==0 for r in rows)

def test_first_time_usable_pairs_distinct_from_completed_requests():
    r=json.loads(Path('outputs/intermediate/data_audit/readiness.json').read_text(encoding='utf-8'))
    e=r['evidence']; x=e['first_bus_xml_audit']
    assert x['reconstructed_request_universe']==e['OA-15334_request_universe']
    assert x['valid_pairs_matched_to_request_universe']==1947
    assert x['valid_pairs_outside_request_universe']==0
    assert x['valid_pairs_matched_to_request_universe']<e['OA-15334_completed_requests']==1999
