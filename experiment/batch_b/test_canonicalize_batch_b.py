"""Focused tests for the Batch B canonical-artifact helper."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
HELPER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HELPER_DIR))

import canonicalize_batch_b as canonical  # pylint: disable=wrong-import-position
import runtime_usage_probe as probe  # pylint: disable=wrong-import-position


def _dictionary_probe(argv_path: str, digest: str) -> dict:
    return {
        'dictionary_usage': [{
            'argv_index': 7,
            'argv_path': argv_path,
            'entries': [{
                'size': 11,
                'content_sha256': digest,
            }],
        }],
    }


def test_actual_x_path_has_priority_over_unselected_dictionary_paths():
    argv = [
        './afl-fuzz',
        '-x',
        './actual.dict',
        '-c',
        '/out/cmplog/target',
        '--',
        '/out/target',
    ]
    assert probe.actual_x_argv_paths(argv) == [(1, './actual.dict')]


def test_same_dictionary_bytes_at_different_paths_have_same_signature():
    digest = hashlib.sha256(b'unchanged bytes').hexdigest()
    left = _dictionary_probe('/out/afl++.dict', digest)
    right = _dictionary_probe('/some/other/path/afl++.dict', digest)
    assert canonical.dictionary_signature(left) == canonical.dictionary_signature(
        right)


def test_same_token_multiset_in_a_different_sequence_changes_raw_bytes():
    first = b'"A"\n"B"\n'
    second = b'"B"\n"A"\n'
    assert hashlib.sha256(first).hexdigest() != hashlib.sha256(second).hexdigest()
    assert probe.token_multiset_from_bytes(
        first) == probe.token_multiset_from_bytes(second)


def test_no_actual_dictionary_is_reported_as_missing():
    assert canonical.dictionary_signature({'dictionary_usage': []}) is None


def test_plan_has_one_canonical_builder_per_benchmark_and_30_new_runners():
    planned = canonical.build_plan(
        ROOT, 'gcr.io/fuzzbench-batchb-focused', 'test-canonical')
    canonical_builders = [
        spec for spec in planned if spec.stage == 'canonical-builder'
    ]
    runners = [spec for spec in planned if spec.stage == 'runner']
    assert len(canonical_builders) == 5
    assert len(runners) == 30
    assert all('/canonical-runners/test-canonical/' in spec.image
               for spec in runners)
    assert all('/runners/batchb_' not in spec.image for spec in runners)


def test_helper_is_excluded_from_worker_docker_context_and_never_sorts_dicts():
    dockerignore = (ROOT / '.dockerignore').read_text(encoding='utf-8')
    assert 'experiment/batch_b/' in dockerignore.splitlines()
    source = (HELPER_DIR / 'canonicalize_batch_b.py').read_text(
        encoding='utf-8')
    probe_source = (HELPER_DIR / 'runtime_usage_probe.py').read_text(
        encoding='utf-8')
    assert 'sort -u' not in source
    assert 'sort -u' not in probe_source
