#!/usr/bin/env python3
"""Capture the actual Batch B AFL argv without launching afl-fuzz.

The host-side canonicalization helper mounts this file read-only into a runner
or canonical-builder image. It calls the real variant fuzzer function and
intercepts only the final subprocess call, so every recorded -x and -c option
comes from the same runtime path that a trial uses.
"""

from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any

from common import fuzzer_utils
from fuzzers import batchb_common


COMMON_RUNTIME_ENV = (
    'AFL_BANDIT_REWARD',
    'AFL_BANDIT_REWARD_FORMULA',
    'AFL_ADARARE_CONTEXTUAL',
    'AFL_ADARARE_ALPHA',
    'AFL_ADARARE_REVISIT_MS',
    'AFL_ADARARE_MIX_P',
    'AFL_ADARARE_DICT_ENABLE',
    'AFL_ADARARE_REWARD_ALPHA',
    'AFL_ADARARE_REWARD_BETA',
    'AFL_ADARARE_REWARD_GAMMA',
    'AFL_BANDIT_DEBUG',
    'AFL_BANDIT_DEBUG_PATH',
    'AFL_NO_UI',
    'AFL_SKIP_CPUFREQ',
    'AFL_NO_AFFINITY',
    'AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES',
    'AFL_SKIP_CRASHES',
    'AFL_SHUFFLE_QUEUE',
    'AFL_IGNORE_UNKNOWN_ENVS',
    'AFL_FAST_CAL',
    'AFL_NO_WARN_INSTABILITY',
    'AFL_DISABLE_TRIM',
    'AFL_CMPLOG_ONLY_NEW',
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _root_label(path: str) -> str:
    if path == '/afl/dictionaries' or path.startswith('/afl/dictionaries/'):
        return 'afl_dictionaries'
    if path == '/out' or path.startswith('/out/'):
        return 'out'
    return 'other'


def token_multiset_from_bytes(raw: bytes) -> list[dict[str, Any]]:
    """Describe dictionary lines without changing their raw byte sequence."""
    counts = Counter(raw.splitlines(keepends=True))
    return [{
        'token_b64': base64.b64encode(token).decode('ascii'),
        'token_sha256': _sha256_bytes(token),
        'multiplicity': count,
    } for token, count in sorted(counts.items())]


def actual_x_argv_paths(argv: list[str]) -> list[tuple[int, str]]:
    """Return only paths selected by actual -x options in the final argv."""
    return [(index, argv[index + 1]) for index, token in enumerate(argv)
            if token == '-x' and index + 1 < len(argv)]


def _describe_file(path: str, relative_path: str) -> dict[str, Any]:
    item_stat = os.stat(path)
    return {
        'relative_path': relative_path,
        'absolute_path': path,
        'mode': oct(stat.S_IMODE(item_stat.st_mode)),
        'size': item_stat.st_size,
        'mtime_ns': item_stat.st_mtime_ns,
        'content_sha256': _sha256_file(path),
        'token_multiset': token_multiset_from_bytes(Path(path).read_bytes()),
    }


def _describe_dictionary_path(path: str, argv_index: int,
                              argv_path: str) -> dict[str, Any]:
    resolved = os.path.realpath(path)
    record: dict[str, Any] = {
        'argv_index': argv_index,
        'argv_path': argv_path,
        'resolved_path': resolved,
        'root_label': _root_label(resolved),
        'entries': [],
    }
    if os.path.isfile(resolved):
        record.update(kind='file', root_path=os.path.dirname(resolved))
        record['entries'].append(
            _describe_file(resolved, os.path.basename(resolved)))
        return record
    if os.path.isdir(resolved):
        record.update(kind='directory', root_path=resolved)
        for current, directories, files in os.walk(resolved):
            directories.sort()
            for filename in sorted(files):
                item = os.path.join(current, filename)
                if not os.path.isfile(item):
                    continue
                record['entries'].append(
                    _describe_file(item, os.path.relpath(item, resolved)))
        return record
    record.update(kind='missing', root_path='')
    return record


def _describe_artifact(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {'path': path, 'exists': False, 'size': None, 'sha256': None}
    item_stat = os.stat(path)
    return {
        'path': path,
        'exists': True,
        'size': item_stat.st_size,
        'sha256': _sha256_file(path),
    }


def _seed_manifest(root: str) -> list[dict[str, Any]]:
    if not os.path.isdir(root):
        return []
    entries = []
    for current, directories, files in os.walk(root):
        directories.sort()
        for filename in sorted(files):
            item = os.path.join(current, filename)
            if not os.path.isfile(item):
                continue
            item_stat = os.stat(item)
            entries.append({
                'relative_path': os.path.relpath(item, root),
                'size': item_stat.st_size,
                'sha256': _sha256_file(item),
            })
    return entries


def _runtime_env(variant: str) -> dict[str, str]:
    keys = set(COMMON_RUNTIME_ENV)
    keys.update(batchb_common.VARIANT_CONFIG[variant]['env'])
    return {key: os.environ.get(key, '') for key in sorted(keys)}


def _capture() -> dict[str, Any]:
    variant = os.environ['BATCHB_PROBE_VARIANT']
    target = os.environ['BATCHB_PROBE_TARGET']
    target_name = os.environ['BATCHB_PROBE_TARGET_NAME']
    if variant not in batchb_common.VARIANT_CONFIG:
        raise ValueError(f'Unknown Batch B variant: {variant}')

    captured: dict[str, Any] = {}
    original_check_call = batchb_common.afl_fuzzer.subprocess.check_call

    def capture_check_call(command, *args, **kwargs):
        del args, kwargs
        captured['afl_argv'] = list(command)
        captured['runtime_env'] = _runtime_env(variant)
        return 0

    batchb_common.afl_fuzzer.subprocess.check_call = capture_check_call
    try:
        input_dir = Path('/tmp/batchb-canonical-probe-input')
        output_dir = Path('/tmp/batchb-canonical-probe-output')
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        module = __import__(f'fuzzers.{variant}.fuzzer', fromlist=['fuzzer'])
        module.fuzz(str(input_dir), str(output_dir), target)
    finally:
        batchb_common.afl_fuzzer.subprocess.check_call = original_check_call

    argv = captured.get('afl_argv')
    if not argv:
        raise RuntimeError('Batch B probe did not observe the final afl-fuzz argv')

    dictionaries = []
    cmplog = []
    for index, argv_path in actual_x_argv_paths(argv):
        effective_path = (argv_path if os.path.isabs(argv_path) else
                          os.path.join(os.getcwd(), argv_path))
        dictionaries.append(
            _describe_dictionary_path(effective_path, index, argv_path))
    for index, token in enumerate(argv):
        if token == '-c' and index + 1 < len(argv):
            cmplog.append(argv[index + 1])

    target_actual = fuzzer_utils.get_fuzz_target_binary('/out', target_name)
    effective_target = target_actual or target
    effective_cmplog = os.path.join(os.path.dirname(effective_target),
                                    'cmplog',
                                    os.path.basename(effective_target))
    return {
        'cwd': os.getcwd(),
        'variant': variant,
        'target_arg': target,
        'target_actual': target_actual,
        'target_exists': os.path.isfile(effective_target),
        'cmplog_expected': effective_cmplog,
        'cmplog_exists': os.path.isfile(effective_cmplog),
        'afl_argv': argv,
        'cmplog_argv': cmplog,
        'dictionary_usage': dictionaries,
        'runtime_env': captured['runtime_env'],
        'artifacts': {
            'target': _describe_artifact(effective_target),
            'cmplog': _describe_artifact(effective_cmplog),
            'afl_fuzz': _describe_artifact('/out/afl-fuzz'),
        },
        'seed_manifest': _seed_manifest('/out/seeds'),
        'afl_fuzz_path': shutil.which('afl-fuzz'),
    }


if __name__ == '__main__':
    print('BATCHB_PROBE_JSON=' + json.dumps(_capture(), sort_keys=True))
