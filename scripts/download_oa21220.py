"""Authorized public, unauthenticated September 2026 OA-21220 acquisition.

Immutable existing files are reused; no credentials or .env files are read.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

PAGE='https://data.seoul.go.kr/dataList/OA-21220/F/1/datasetView.do'
ENDPOINT='https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false'
ROOT=Path('data/raw/bus/OA-21220')
AUDIT=Path('outputs/intermediate/data_audit')
SEQS=['260914','260921','260928','261005','261012']

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--download',action='store_true'); args=parser.parse_args()
    if not args.download: raise SystemExit('Explicit --download required; local audit is scripts/audit_oa21220.py')
    page=(AUDIT/'OA-21220_page.html').read_text(encoding='utf-8')
    records=[]; ROOT.mkdir(parents=True,exist_ok=True)
    for seq in SEQS:
        match=re.search(r'title="([^"]+\.zip)" onclick="javascript:downloadFile\(\''+seq+r"'\)",page)
        if not match: raise ValueError('Official listing missing seq '+seq)
        name=match.group(1); p=ROOT/name
        if not p.exists():
            req=urllib.request.Request(ENDPOINT,data=urllib.parse.urlencode({'infId':'OA-21220','infSeq':'3','seq':seq,'seqNo':''}).encode(),headers={'Referer':PAGE})
            temp=p.with_suffix('.zip.part')
            with urllib.request.urlopen(req,timeout=120) as r, temp.open('xb') as out:
                size=0
                while b:=r.read(2**20):
                    size+=len(b)
                    if size>100_000_000: raise ValueError('Exceeded per-file safety cap')
                    out.write(b)
            with zipfile.ZipFile(temp) as z:
                if z.testzip(): raise ValueError('CRC check failed')
            temp.replace(p)
        members=[]
        with zipfile.ZipFile(p) as z:
            for info in z.infolist():
                target=(ROOT/'extracted'/info.filename).resolve()
                if not target.is_relative_to((ROOT/'extracted').resolve()): raise ValueError('Unsafe ZIP member')
                if info.is_dir(): continue
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():
                    with z.open(info) as src,target.open('xb') as dst:
                        while b:=src.read(2**20):dst.write(b)
                members.append({'path':target.relative_to(Path.cwd()).as_posix(),'bytes':target.stat().st_size,'sha256':digest(target)})
        records.append({'filename':name,'path':p.as_posix(),'seq':seq,'bytes':p.stat().st_size,'sha256':digest(p),'members':members})
        print(name,p.stat().st_size,'bytes',len(members),'members',flush=True)
    manifest={'dataset_id':'OA-21220','source_url':PAGE,'download_endpoint':ENDPOINT,'method':'POST','form':{'infId':'OA-21220','infSeq':'3','seqNo':''},'retrieved_at':datetime.now(timezone.utc).isoformat(),'license':'공공누리 1유형: 출처표시 (상업적 이용 및 변경 가능)','expected_total_download_mb':67.0,'records':records,'immutable_raw_policy':'exclusive create; existing files never overwritten'}
    (AUDIT/'OA-21220_download_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
