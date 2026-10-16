"""Validate contract gates and source fingerprints without network access."""
import argparse
import json
import re
from pathlib import Path
from src.data.audit import sha256

MODES={'full':(True,True,True),'demand_only':(True,False,False),'transit_only':(False,True,False),'separate_only':(True,True,False),'blocked':(False,False,False)}
REQUIRED={'dataset_id','status','path','sha256','row_grain','primary_key','required_columns','time_zone','crs','temporal_coverage','spatial_coverage','allowed_uses','block_reason'}

def validate(contract, readiness, verify_hashes=False):
    assert readiness['mode'] in MODES, 'Unknown mode'
    flags=tuple(readiness[x] for x in ['demand_ready','transit_ready','join_ready'])
    assert all(type(v) is bool for v in flags), 'Readiness flags must be boolean'
    assert flags==MODES[readiness['mode']], 'Mode/flag invariant broken'
    assert readiness['join_ready'] is False and readiness['mode']!='full', 'User prohibits full or joined inference'
    assert readiness['evidence'] and readiness['unavailable_outputs']
    ids=[]
    for row in contract['datasets']:
        assert REQUIRED<=set(row), 'Missing dataset fields'
        ids.append(row['dataset_id'])
        assert row['status'] in ['available_limited','unavailable']
        if row['status']=='unavailable':
            assert row['block_reason'] and not row['path']
        else:
            assert row['path'] and set(row['path'])==set(row['sha256'])
            for p in row['path']:
                assert Path(p).is_file(), f'Missing input: {p}'
                assert re.fullmatch('[a-f0-9]{64}',row['sha256'][p]), 'Invalid SHA256'
                if verify_hashes: assert sha256(p)==row['sha256'][p], f'Input fingerprint changed: {p}'
    assert len(ids)==len(set(ids)), 'Duplicate dataset ids'
    assert {'OA-22300','OA-22657','OA-22298','OA-12913','OA-15334','OA-1095','OA-15067','OA-21230','OA-21231','OA-21232','OA-21233','data-go-15143847','data-go-15129688','mobility_codebooks','OA-1094','campus-332','campus-336','survey-interview'}<=set(ids)
    return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--contract',required=True); ap.add_argument('--verify-hashes',action='store_true'); args=ap.parse_args()
    contract=json.loads(Path(args.contract).read_text(encoding='utf-8'))
    readiness=json.loads(Path(contract['readiness_path']).read_text(encoding='utf-8'))
    validate(contract,readiness,args.verify_hashes)
    print(f"Contract valid: {readiness['mode']}; {len(contract['datasets'])} datasets; hashes {'verified' if args.verify_hashes else 'format checked (use --verify-hashes for full content check)'}")

if __name__=='__main__': main()
