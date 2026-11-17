from pathlib import Path
import pytest
from seed import read_seed, FIELDS


def test_public_seed_has_complete_rows_and_preserves_quoted_commas():
    sites = read_seed(Path('data/seed/paragon_public_properties.csv'))
    assert len(sites) == 36
    assert '58,193' in sites[1]['notes']
    assert sites[25]['reference_lat'] == '41.642480'
    assert sites[25]['source_url'].endswith('/the-vineyards-shopping-center/')
    assert not sites[20]['reference_lat']


def test_malformed_seed_is_rejected_before_lookups(tmp_path):
    path = tmp_path/'seed.csv'
    path.write_text(','.join(FIELDS)+'\nP01,too,few\n')
    with pytest.raises(ValueError, match='expected 13 columns'):
        read_seed(path)
