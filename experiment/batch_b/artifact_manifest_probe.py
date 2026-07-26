#!/usr/bin/env python3
"""Describe copied canonical artifacts without importing FuzzBench runtime code."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _describe_file(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {'path': path, 'exists': False, 'size': None, 'sha256': None}
    item = os.stat(path)
    return {
        'path': path,
        'exists': True,
        'size': item.st_size,
        'sha256': _sha256_file(path),
    }


def _manifest(root: str) -> list[dict[str, Any]]:
    if not os.path.isdir(root):
        return []
    rows = []
    for current, directories, files in os.walk(root):
        directories.sort()
        for filename in sorted(files):
            path = os.path.join(current, filename)
            if not os.path.isfile(path):
                continue
            item = os.stat(path)
            rows.append({
                'absolute_path': path,
                'relative_path': os.path.relpath(path, root),
                'size': item.st_size,
                'sha256': _sha256_file(path),
            })
    return rows


def main() -> None:
    target_name = os.environ['BATCHB_PROBE_TARGET_NAME']
    target = f'/out/{target_name}'
    cmplog = f'/out/cmplog/{target_name}'
    print('BATCHB_ARTIFACT_JSON=' + json.dumps({
        'artifacts': {
            'target': _describe_file(target),
            'cmplog': _describe_file(cmplog),
            'afl_fuzz': _describe_file('/out/afl-fuzz'),
        },
        'seed_manifest': _manifest('/out/seeds'),
        'file_manifest': _manifest('/out') + _manifest('/afl/dictionaries'),
    }, sort_keys=True))


if __name__ == '__main__':
    main()
