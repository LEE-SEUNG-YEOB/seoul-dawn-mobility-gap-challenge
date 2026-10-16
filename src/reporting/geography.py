"""Exact-name, audited crosswalk; never equate SGIS and mobility codes."""
from pathlib import Path
import json

import pandas as pd
import shapefile
from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform


def normalized_name(name):
    """Normalize punctuation only; do not merge renamed or split districts."""
    return name.replace('·', '.')


def load_seoul_geography(root: Path):
    boundary_root = root / 'data/raw/boundaries'
    dong_path = next(boundary_root.rglob('*dong*.shp'))
    district_path = next(boundary_root.rglob('*sigungu*.shp'))
    districts = {r['SIGUNGU_CD']: r['SIGUNGU_NM'] for r in
                 shapefile.Reader(str(district_path), encoding='utf-8').records()}
    code_path = root / 'data/reference/mobility_codebooks/전국_행정동_코드정보/SEOUL_ADMI/ADMI_202608.csv'
    codes = pd.read_csv(code_path, dtype=str, encoding='utf-8-sig')
    codes = codes[codes.SIDO_NM == '서울특별시']
    codes['normalized_name'] = codes.ADMI_NM.map(normalized_name)
    if codes.duplicated(['SGG_NM', 'normalized_name']).any():
        raise ValueError('Ambiguous district/dong names in mobility codebook')
    lookup = {(r.SGG_NM, r.normalized_name): r.ADMI_CD for r in codes.itertuples()}
    project = Transformer.from_crs(CRS.from_wkt(dong_path.with_suffix('.prj').read_text()),
                                  'EPSG:4326', always_xy=True).transform
    features, audit = [], []
    seen = set()
    reader = shapefile.Reader(str(dong_path), encoding='utf-8')
    for sr in reader.iterShapeRecords():
        code = sr.record['ADM_CD']
        if not code.startswith('11'):
            continue
        district = districts[code[:5]]
        name = sr.record['ADM_NM']
        mobility_id = lookup.get((district, normalized_name(name)))
        audit.append({'boundary_id': code, 'district': district, 'dong_name': name,
                      'mobility_id': mobility_id, 'match_status': 'normalized_exact_name' if mobility_id else 'unknown',
                      'boundary_date': sr.record['BASE_DATE'], 'codebook_month': '202608'})
        if mobility_id is not None and mobility_id in seen:
            raise ValueError('Multiple polygons matched one mobility code')
        if mobility_id is not None:
            seen.add(mobility_id)
        geom = transform(project, shape(sr.shape.__geo_interface__))
        if not geom.is_valid:
            raise ValueError(f'Invalid geometry: {code}')
        features.append({'type': 'Feature', 'geometry': mapping(geom), 'properties': {
            'mobility_id': mobility_id, 'boundary_id': code, 'district': district,
            'dong_name': name, 'boundary_date': sr.record['BASE_DATE'],
            'codebook_month': '202608', 'match_method': 'unique_district_and_dong_name_with_middle_dot_normalization' if mobility_id else 'unknown',
            'temporal_caveat': '2025Q2 boundary; 202608 names; not verified September 2026 boundary'}})
    for r in codes.itertuples():
        if r.ADMI_CD not in seen:
            audit.append({'boundary_id': None, 'district': r.SGG_NM, 'dong_name': r.ADMI_NM,
                          'mobility_id': r.ADMI_CD, 'match_status': 'unknown',
                          'boundary_date': None, 'codebook_month': '202608'})
    return features, pd.DataFrame(audit), [dong_path, district_path, code_path]


def write_geojson(path: Path, features):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'type': 'FeatureCollection', 'features': features},
                              ensure_ascii=False, separators=(',', ':'), allow_nan=False), encoding='utf-8')
