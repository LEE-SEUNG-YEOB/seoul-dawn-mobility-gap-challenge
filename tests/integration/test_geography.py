from pathlib import Path

from src.reporting.geography import load_seoul_geography, normalized_name


def test_name_normalization_does_not_merge_different_dongs():
    assert normalized_name('종로1·2·3·4가동') == '종로1.2.3.4가동'
    assert normalized_name('용신동') != normalized_name('용두동')


def test_local_crosswalk_is_unique_and_within_seoul():
    features, audit, _ = load_seoul_geography(Path('.'))
    ids = [f['properties']['mobility_id'] for f in features if f['properties']['mobility_id']]
    assert len(ids) == len(set(ids)) == 425
    assert set(audit.loc[audit.match_status == 'unknown', 'dong_name']) == {'용신동', '용두동', '신설동'}
    from shapely.geometry import shape
    for feature in features:
        west, south, east, north = shape(feature['geometry']).bounds
        assert 126 < west < east < 128
        assert 37 < south < north < 38
