"""A checkout must contain the exact reviewed PDFs and safe source paths."""
import hashlib
import json
from pathlib import Path

import pytest

from compass.config import Settings
from compass.ingestion import pdf_path


def test_bundled_pdfs_match_reviewed_sources():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / 'sources.json').read_text(encoding='utf-8'))
    assert len(spec['sources']) == 4
    for source in spec['sources']:
        path = pdf_path(Settings(root=root), source)
        assert path.parent == root / 'dataset'
        assert path.read_bytes().startswith(b'%PDF-')
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source['reviewed_sha256']


def test_packaged_source_preferred_with_legacy_fallback(tmp_path):
    settings = Settings(root=tmp_path)
    old = tmp_path / 'data/originals/policy.pdf'
    old.parent.mkdir(parents=True)
    old.write_bytes(b'legacy')
    source = {'filename': 'policy.pdf'}
    assert pdf_path(settings, source) == old
    packaged = tmp_path / 'dataset/policy.pdf'
    packaged.parent.mkdir()
    packaged.write_bytes(b'packaged')
    assert pdf_path(settings, source) == packaged


@pytest.mark.parametrize('filename', ['../policy.pdf', 'nested/policy.pdf', 'policy.txt'])
def test_source_path_cannot_escape_dataset(tmp_path, filename):
    with pytest.raises(ValueError, match='directly inside'):
        pdf_path(Settings(root=tmp_path), {'filename': filename})
