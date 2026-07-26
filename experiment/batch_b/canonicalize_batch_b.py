#!/usr/bin/env python3
"""Build one canonical Batch B artifact per benchmark and audit all runners.

This helper intentionally creates new image names. It never retags, removes,
or consumes the prior per-variant builder or runner images as build inputs.
The only variant-specific build input for a final runner is its unchanged
runner.Dockerfile, which supplies the existing runtime ENV values.
"""

from __future__ import annotations

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import Any, Iterable


VARIANTS = (
    'batchb_aflpp_default',
    'batchb_aflpp_cmplog_matched',
    'batchb_aflpp_shadow',
    'batchb_adarare_full',
    'batchb_adarare_no_a6',
    'batchb_adarare_no_rarity',
)
BENCHMARKS = (
    'curl_curl_fuzzer_http',
    'lcms_cms_transform_fuzzer',
    'proj4_proj_crs_to_crs_fuzzer',
    'sqlite3_ossfuzz',
    'openh264_decoder_fuzzer',
)
CANONICAL_BUILD_FUZZER = 'batchb_aflpp_default'
EXPECTED_PARENT = '43c79d7e2eca92229bebd4ecbcb121e5da1dd91f'
RUNNER_CONCURRENCY = 6
MAX_TRANSIENT_ATTEMPTS = 3
TRANSIENT_MARKERS = (
    'tls handshake timeout',
    'tls handshake',
    'x509:',
    'certificate verify failed',
    'proxyconnect',
    'proxy error',
    'connection reset',
    'connection refused',
    'i/o timeout',
    'network is unreachable',
    'temporary failure',
    'temporarily unavailable',
    'unexpected eof',
    'context deadline exceeded',
)


class GateError(RuntimeError):
    """A strict provenance or build gate failed."""


@dataclass(frozen=True)
class BuildSpec:
    stage: str
    benchmark: str
    variant: str
    image: str
    dockerfile: Path
    context: Path
    build_args: tuple[tuple[str, str], ...]


@dataclass
class BuildRecord:
    stage: str
    benchmark: str
    variant: str
    image: str
    start_time: str
    end_time: str
    duration_sec: float
    attempts: int
    exit_code: int
    status: str
    log_path: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8')


def write_tsv(path: Path, header: Iterable[str],
              rows: Iterable[Iterable[Any]]) -> None:
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle, delimiter='\t', lineterminator='\n')
        writer.writerow(list(header))
        writer.writerows(rows)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle, delimiter='\t'))


def run_output(command: list[str], cwd: Path) -> str:
    proc = subprocess.run(command,
                          cwd=cwd,
                          text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          check=False)
    if proc.returncode:
        raise GateError(
            f'command failed ({proc.returncode}): {command!r}\n{proc.stderr}')
    return proc.stdout


def git_output(repo: Path, *arguments: str) -> str:
    return run_output(['git', *arguments], repo).strip()


def image_name(namespace: str, family: str, run_id: str,
               *parts: str) -> str:
    return '/'.join((namespace, family, run_id, *parts))


def canonical_project_image(namespace: str, run_id: str,
                            benchmark: str) -> str:
    return image_name(namespace, 'canonical-project-builders', run_id,
                      benchmark)


def canonical_intermediate_image(namespace: str, run_id: str,
                                 benchmark: str) -> str:
    return image_name(namespace, 'canonical-builders', run_id,
                      f'{benchmark}-intermediate')


def canonical_builder_image(namespace: str, run_id: str,
                            benchmark: str) -> str:
    return image_name(namespace, 'canonical-builders', run_id, benchmark)


def canonical_runner_intermediate_image(namespace: str, run_id: str,
                                        variant: str) -> str:
    return image_name(namespace, 'canonical-runner-intermediates', run_id,
                      variant)


def canonical_runner_image(namespace: str, run_id: str, variant: str,
                           benchmark: str) -> str:
    return image_name(namespace, 'canonical-runners', run_id, variant,
                      benchmark)


def extract_function_ast(path: Path, name: str) -> str:
    module = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.dump(node, include_attributes=False)
    raise GateError(f'{path} has no function {name}')


def validate_batchb_build_equivalence(repo: Path) -> dict[str, Any]:
    """Prove the selected build wrapper is not a variant-specific artifact."""
    reference_builder = sha256_file(
        repo / 'fuzzers' / CANONICAL_BUILD_FUZZER / 'builder.Dockerfile')
    reference_build = extract_function_ast(
        repo / 'fuzzers' / CANONICAL_BUILD_FUZZER / 'fuzzer.py', 'build')
    records = []
    for variant in VARIANTS:
        builder_path = repo / 'fuzzers' / variant / 'builder.Dockerfile'
        fuzzer_path = repo / 'fuzzers' / variant / 'fuzzer.py'
        builder_hash = sha256_file(builder_path)
        build_ast = extract_function_ast(fuzzer_path, 'build')
        if builder_hash != reference_builder:
            raise GateError(
                f'Batch B builder Dockerfile differs for {variant}: '
                f'{builder_hash} != {reference_builder}')
        if build_ast != reference_build:
            raise GateError(f'Batch B build wrapper differs for {variant}')
        records.append({
            'variant': variant,
            'builder_dockerfile_sha256': builder_hash,
            'build_function_ast_sha256': sha256_bytes(build_ast.encode()),
        })
    return {
        'canonical_build_fuzzer': CANONICAL_BUILD_FUZZER,
        'shared_builder_dockerfile_sha256': reference_builder,
        'build_wrapper_records': records,
    }


def validate_changed_paths(repo: Path, parent: str, commit: str) -> list[str]:
    changed = [
        value for value in git_output(repo, 'diff', '--name-only', parent,
                                      commit).splitlines() if value
    ]
    allowed = {'.dockerignore'}
    if (not changed or any(path not in allowed and
                           not path.startswith('experiment/batch_b/')
                           for path in changed)):
        raise GateError(
            'canonicalization commit changed a runtime/build path outside '
            f'the dedicated helper: {changed!r}')
    dockerignore = (repo / '.dockerignore').read_text(encoding='utf-8').splitlines()
    if 'experiment/batch_b/' not in dockerignore:
        raise GateError(
            '.dockerignore must exclude experiment/batch_b/ so the helper '
            'does not change worker-image contents')
    return changed


def read_yaml_scalar(path: Path, key: str) -> str:
    matcher = re.compile(rf'^\s*{re.escape(key)}\s*:\s*(.*?)\s*$')
    for line in path.read_text(encoding='utf-8').splitlines():
        found = matcher.match(line)
        if found:
            return found.group(1).strip().strip('"').strip("'")
    raise GateError(f'missing {key} in {path}')


def build_plan(repo: Path, namespace: str,
               run_id: str) -> list[BuildSpec]:
    """Return the full planned build DAG without running Docker."""
    specs: list[BuildSpec] = []
    for benchmark in BENCHMARKS:
        project = canonical_project_image(namespace, run_id, benchmark)
        intermediate = canonical_intermediate_image(namespace, run_id,
                                                     benchmark)
        canonical = canonical_builder_image(namespace, run_id, benchmark)
        specs.extend((
            BuildSpec(
                'canonical-project-builder', benchmark, '', project,
                repo / 'benchmarks' / benchmark / 'Dockerfile',
                repo / 'benchmarks' / benchmark,
                ()),
            BuildSpec(
                'canonical-builder-intermediate', benchmark,
                CANONICAL_BUILD_FUZZER, intermediate,
                repo / 'fuzzers' / CANONICAL_BUILD_FUZZER /
                'builder.Dockerfile',
                repo / 'fuzzers' / CANONICAL_BUILD_FUZZER,
                (('parent_image', project),)),
            BuildSpec(
                'canonical-builder', benchmark, CANONICAL_BUILD_FUZZER,
                canonical, repo / 'docker' / 'benchmark-builder' /
                'Dockerfile', repo,
                (('image_namespace', namespace), ('parent_image',
                                                   intermediate),
                 ('fuzzer', CANONICAL_BUILD_FUZZER),
                 ('benchmark', benchmark))),
        ))
    for variant in VARIANTS:
        intermediate = canonical_runner_intermediate_image(namespace, run_id,
                                                            variant)
        specs.append(
            BuildSpec('canonical-runner-intermediate', '', variant,
                      intermediate,
                      repo / 'fuzzers' / variant / 'runner.Dockerfile',
                      repo / 'fuzzers' / variant,
                      (('image_namespace', namespace),)))
    for benchmark in BENCHMARKS:
        canonical = canonical_builder_image(namespace, run_id, benchmark)
        for variant in VARIANTS:
            specs.append(
                BuildSpec(
                    'runner', benchmark, variant,
                    canonical_runner_image(namespace, run_id, variant,
                                           benchmark),
                    repo / 'experiment' / 'batch_b' /
                    'canonical_runner.Dockerfile', repo,
                    (('canonical_builder_image', canonical),
                     ('parent_runner_image',
                      canonical_runner_intermediate_image(
                          namespace, run_id, variant)),
                     ('image_namespace', namespace), ('fuzzer', variant),
                     ('benchmark', benchmark))))
    return specs


class CommandLog:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()

    def add(self, value: dict[str, Any]) -> None:
        with self.lock:
            with self.path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(value, sort_keys=True) + '\n')


def docker_build_command(spec: BuildSpec) -> list[str]:
    command = [
        'docker',
        'build',
        '--network=host',
        '--no-cache',
        '--tag',
        spec.image,
    ]
    for key, value in spec.build_args:
        command.extend(('--build-arg', f'{key}={value}'))
    command.extend(('--file', str(spec.dockerfile), str(spec.context)))
    return command


def is_transient_failure(log_path: Path) -> bool:
    try:
        text = log_path.read_text(encoding='utf-8', errors='replace')[-60000:]
    except OSError:
        return False
    text = text.lower()
    return any(marker in text for marker in TRANSIENT_MARKERS)


def run_build(spec: BuildSpec, repo: Path, logs_dir: Path,
              command_log: CommandLog) -> BuildRecord:
    safe_variant = spec.variant or 'shared'
    log_path = logs_dir / (
        f'{spec.stage}__{spec.benchmark or "shared"}__{safe_variant}.log')
    command = docker_build_command(spec)
    start = utc_now()
    monotonic_start = time.monotonic()
    exit_code = 1
    attempts = 0
    for attempts in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
        command_log.add({
            'timestamp': utc_now(),
            'stage': spec.stage,
            'benchmark': spec.benchmark,
            'variant': spec.variant,
            'image': spec.image,
            'attempt': attempts,
            'command': command,
        })
        with log_path.open('a', encoding='utf-8') as handle:
            handle.write(f'\n=== attempt {attempts}/{MAX_TRANSIENT_ATTEMPTS} ===\n')
            handle.write('command=' + json.dumps(command) + '\n')
            proc = subprocess.run(command,
                                  cwd=repo,
                                  stdout=handle,
                                  stderr=subprocess.STDOUT,
                                  text=True,
                                  check=False)
        exit_code = proc.returncode
        if exit_code == 0:
            break
        if attempts == MAX_TRANSIENT_ATTEMPTS or not is_transient_failure(
                log_path):
            break
        time.sleep(5 * attempts)
    end = utc_now()
    return BuildRecord(
        stage=spec.stage,
        benchmark=spec.benchmark,
        variant=spec.variant,
        image=spec.image,
        start_time=start,
        end_time=end,
        duration_sec=round(time.monotonic() - monotonic_start, 3),
        attempts=attempts,
        exit_code=exit_code,
        status='PASS' if exit_code == 0 else 'FAIL',
        log_path=str(log_path),
    )


def execute_builds(plan: list[BuildSpec], repo: Path, logs_dir: Path,
                   command_log: CommandLog) -> list[BuildRecord]:
    records: list[BuildRecord] = []
    pre_runner = [spec for spec in plan if spec.stage != 'runner']
    runner_specs = [spec for spec in plan if spec.stage == 'runner']
    for spec in pre_runner:
        record = run_build(spec, repo, logs_dir, command_log)
        records.append(record)
        if record.status != 'PASS':
            return records
    with ThreadPoolExecutor(max_workers=RUNNER_CONCURRENCY) as executor:
        future_to_spec = {
            executor.submit(run_build, spec, repo, logs_dir, command_log):
            spec for spec in runner_specs
        }
        for future in as_completed(future_to_spec):
            records.append(future.result())
    return records


def inspect_image(image: str, repo: Path) -> dict[str, Any]:
    output = run_output(['docker', 'image', 'inspect', image], repo)
    value = json.loads(output)[0]
    digests = value.get('RepoDigests') or []
    return {
        'image': image,
        'image_id': value['Id'],
        'repo_digest': ';'.join(digests) if digests else 'LOCAL_ONLY',
        'created': value.get('Created', ''),
        'architecture': value.get('Architecture', ''),
        'os': value.get('Os', ''),
    }


def expected_legacy_images(namespace: str) -> list[str]:
    return [
        f'{namespace}/runners/{variant}/{benchmark}'
        for benchmark in BENCHMARKS for variant in VARIANTS
    ]


def legacy_snapshot(namespace: str, repo: Path) -> list[dict[str, Any]]:
    rows = []
    for image in expected_legacy_images(namespace):
        try:
            rows.append(inspect_image(image, repo))
        except GateError:
            rows.append({
                'image': image,
                'image_id': 'MISSING',
                'repo_digest': 'MISSING',
                'created': '',
                'architecture': '',
                'os': '',
            })
    return rows


def reused_images(namespace: str) -> dict[str, list[str]]:
    return {
        'control': [
            f'{namespace}/base-image',
            f'{namespace}/worker',
            f'{namespace}/dispatcher-image',
        ],
        'coverage': [
            f'{namespace}/builders/coverage/{benchmark}'
            for benchmark in BENCHMARKS
        ],
    }


def validate_reused_images(namespace: str, repo: Path, evidence: Path,
                           before: dict[str, list[dict[str, Any]]]
                           ) -> tuple[list[dict[str, Any]], bool]:
    rows = []
    success = True
    for role, images in reused_images(namespace).items():
        frozen_file = evidence / f'{role}_image_manifest.tsv'
        frozen_by_image = {
            row['image']: row
            for row in read_tsv(frozen_file)
        }
        if set(frozen_by_image) != set(images):
            raise GateError(
                f'frozen {role} manifest does not match the required image '
                f'set: {frozen_file}')
        before_by_image = {row['image']: row for row in before[role]}
        for image in images:
            current = inspect_image(image, repo)
            frozen = frozen_by_image[image]
            previous = before_by_image[image]
            id_matches_frozen = current['image_id'] == frozen['image_id']
            id_stable = current['image_id'] == previous['image_id']
            row_ok = id_matches_frozen and id_stable
            success = success and row_ok
            rows.append({
                'role': role,
                'image': image,
                'frozen_image_id': frozen['image_id'],
                'before_image_id': previous['image_id'],
                'after_image_id': current['image_id'],
                'frozen_id_match': str(id_matches_frozen).lower(),
                'unchanged_during_run': str(id_stable).lower(),
                'status': 'PASS' if row_ok else 'FAIL',
            })
    return rows, success


def collect_reuse_before(namespace: str, repo: Path) -> dict[str,
                                                             list[dict[str,
                                                                       Any]]]:
    return {
        role: [inspect_image(image, repo) for image in images]
        for role, images in reused_images(namespace).items()
    }


def run_probe(repo: Path, image: str, variant: str,
              target_name: str) -> dict[str, Any]:
    probe = repo / 'experiment' / 'batch_b' / 'runtime_usage_probe.py'
    target = f'/out/{target_name}'
    command = [
        'docker',
        'run',
        '--rm',
        '--network=none',
        '--workdir',
        '/out',
        '-e',
        f'BATCHB_PROBE_VARIANT={variant}',
        '-e',
        f'BATCHB_PROBE_TARGET={target}',
        '-e',
        f'BATCHB_PROBE_TARGET_NAME={target_name}',
        '-v',
        f'{probe.resolve()}:/tmp/batchb_runtime_usage_probe.py:ro',
        '--entrypoint',
        'python3',
        image,
        '/tmp/batchb_runtime_usage_probe.py',
    ]
    proc = subprocess.run(command,
                          cwd=repo,
                          text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          check=False)
    if proc.returncode:
        raise GateError(f'probe failed for {image}:\n{proc.stdout}')
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith('BATCHB_PROBE_JSON='):
            return json.loads(line.removeprefix('BATCHB_PROBE_JSON='))
    raise GateError(f'probe did not emit JSON for {image}:\n{proc.stdout}')


def run_artifact_probe(repo: Path, image: str,
                       target_name: str) -> dict[str, Any]:
    """Inspect a canonical builder without importing its runtime source tree."""
    probe = repo / 'experiment' / 'batch_b' / 'artifact_manifest_probe.py'
    command = [
        'docker',
        'run',
        '--rm',
        '--network=none',
        '-e',
        f'BATCHB_PROBE_TARGET_NAME={target_name}',
        '-v',
        f'{probe.resolve()}:/tmp/batchb_artifact_manifest_probe.py:ro',
        '--entrypoint',
        'python3',
        image,
        '/tmp/batchb_artifact_manifest_probe.py',
    ]
    proc = subprocess.run(command,
                          cwd=repo,
                          text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,
                          check=False)
    if proc.returncode:
        raise GateError(f'artifact probe failed for {image}:\n{proc.stdout}')
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith('BATCHB_ARTIFACT_JSON='):
            return json.loads(line.removeprefix('BATCHB_ARTIFACT_JSON='))
    raise GateError(
        f'artifact probe did not emit JSON for {image}:\n{proc.stdout}')


def artifact_sha(probe: dict[str, Any], kind: str) -> str:
    item = probe['artifacts'][kind]
    if not item['exists'] or not item['sha256']:
        raise GateError(f'missing {kind} artifact at {item["path"]}')
    return item['sha256']


def dictionary_signature(probe: dict[str, Any]) -> str | None:
    uses = probe['dictionary_usage']
    if not uses:
        return None
    lines = []
    for use in sorted(uses, key=lambda item: item['argv_index']):
        for file_order, item in enumerate(use['entries']):
            lines.append(
                f'{use["argv_index"]}\t{file_order}\t{item["size"]}\t'
                f'{item["content_sha256"]}\n')
    if not lines:
        return None
    return sha256_bytes(''.join(lines).encode('utf-8'))


def canonical_dictionary_signature(canonical: dict[str, Any],
                                   runner: dict[str, Any]) -> str | None:
    """Hash canonical bytes at the exact actual -x paths from one runner."""
    uses = runner['dictionary_usage']
    if not uses:
        return None
    canonical_files = {
        item['absolute_path']: item
        for item in canonical['file_manifest']
    }
    lines = []
    for use in sorted(uses, key=lambda item: item['argv_index']):
        for file_order, runner_item in enumerate(use['entries']):
            canonical_item = canonical_files.get(runner_item['absolute_path'])
            if (canonical_item is None or
                    canonical_item['size'] != runner_item['size']):
                return None
            lines.append(
                f'{use["argv_index"]}\t{file_order}\t'
                f'{canonical_item["size"]}\t'
                f'{canonical_item["sha256"]}\n')
    if not lines:
        return None
    return sha256_bytes(''.join(lines).encode('utf-8'))


def corpus_signature(probe: dict[str, Any]) -> str:
    lines = [
        f'{item["relative_path"]}\t{item["size"]}\t{item["sha256"]}\n'
        for item in probe['seed_manifest']
    ]
    return sha256_bytes(''.join(lines).encode('utf-8'))


def expected_variant_config(repo: Path) -> dict[str, dict[str, Any]]:
    """Import only static configuration from the current source tree."""
    source = repo / 'fuzzers' / 'batchb_common.py'
    module = ast.parse(source.read_text(encoding='utf-8'), filename=str(source))
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and
                   target.id == 'VARIANT_CONFIG' for target in node.targets):
                value = ast.literal_eval(node.value)
                return value
    raise GateError('could not statically read VARIANT_CONFIG')


def evaluate_gates(canonical_probes: dict[str, dict[str, Any]],
                   runner_probes: dict[tuple[str, str], dict[str, Any]],
                   config: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures = []
    details = {}
    for benchmark in BENCHMARKS:
        canonical = canonical_probes[benchmark]
        canonical_artifacts = {
            kind: artifact_sha(canonical, kind)
            for kind in ('target', 'cmplog', 'afl_fuzz')
        }
        canonical_corpus = corpus_signature(canonical)
        benchmark_rows = []
        canonical_dictionary_values = []
        for variant in VARIANTS:
            probe = runner_probes[(benchmark, variant)]
            artifact_match = all(
                artifact_sha(probe, kind) == digest
                for kind, digest in canonical_artifacts.items())
            runner_dictionary = dictionary_signature(probe)
            canonical_dictionary = canonical_dictionary_signature(
                canonical, probe)
            canonical_dictionary_values.append(canonical_dictionary)
            dictionary_match = (runner_dictionary is not None and
                                runner_dictionary == canonical_dictionary)
            corpus_match = corpus_signature(probe) == canonical_corpus
            expected = config[variant]
            actual_cmplog = probe['cmplog_argv']
            cmplog_match = (
                bool(actual_cmplog) == bool(expected['use_cmplog']) and
                (not actual_cmplog or
                 actual_cmplog == [probe['cmplog_expected']]))
            env_match = all(
                probe['runtime_env'].get(key) == value
                for key, value in expected['env'].items())
            row_ok = (artifact_match and dictionary_match and corpus_match and
                      cmplog_match and env_match)
            if not row_ok:
                failures.append(
                    f'{benchmark}/{variant}: artifact={artifact_match} '
                    f'dictionary={dictionary_match} corpus={corpus_match} '
                    f'cmplog={cmplog_match} env={env_match}')
            benchmark_rows.append({
                'variant': variant,
                'artifacts_equal_canonical': artifact_match,
                'dictionary_raw_bytes_equal_canonical': dictionary_match,
                'corpus_equal_canonical': corpus_match,
                'cmplog_configuration_matches': cmplog_match,
                'runtime_env_matches': env_match,
                'status': 'PASS' if row_ok else 'FAIL',
            })
        details[benchmark] = {
            'canonical_target_sha256': canonical_artifacts['target'],
            'canonical_cmplog_sha256': canonical_artifacts['cmplog'],
            'canonical_afl_fuzz_sha256': canonical_artifacts['afl_fuzz'],
            'canonical_dictionary_signatures':
            canonical_dictionary_values,
            'canonical_corpus_signature': canonical_corpus,
            'rows': benchmark_rows,
        }
    return {
        'status': 'PASS' if not failures else 'FAIL',
        'failures': failures,
        'benchmarks': details,
    }


def write_audit_tables(output: Path, repo: Path, namespace: str, run_id: str,
                       canonical_probes: dict[str, dict[str, Any]],
                       runner_probes: dict[tuple[str, str], dict[str, Any]],
                       config: dict[str, dict[str, Any]]) -> None:
    runtime_rows = []
    binary_rows = []
    dictionary_usage_rows = []
    dictionary_raw_rows = []
    token_multiset_rows = []
    token_set_rows = []
    corpus_rows = []
    argv_rows = []
    env_rows = []
    variant_rows = []
    canonical_rows = []
    canonical_file_rows = []

    for benchmark in BENCHMARKS:
        canonical_image = canonical_builder_image(namespace, run_id, benchmark)
        canonical_probe = canonical_probes[benchmark]
        canonical_rows.append([
            benchmark, canonical_image,
            artifact_sha(canonical_probe, 'target'),
            artifact_sha(canonical_probe, 'cmplog'),
            artifact_sha(canonical_probe, 'afl_fuzz'),
            canonical_dictionary_signature(
                canonical_probe,
                runner_probes[(benchmark, CANONICAL_BUILD_FUZZER)]) or
            'NO_DICTIONARY',
            corpus_signature(canonical_probe),
        ])
        for item in canonical_probe['file_manifest']:
            canonical_file_rows.append([
                benchmark, canonical_image, item['absolute_path'],
                item['relative_path'], item['size'], item['sha256']
            ])
        for variant in VARIANTS:
            image = canonical_runner_image(namespace, run_id, variant,
                                           benchmark)
            info = inspect_image(image, repo)
            probe = runner_probes[(benchmark, variant)]
            dictionary_digest = dictionary_signature(probe) or 'NO_DICTIONARY'
            seed_digest = corpus_signature(probe)
            runtime_rows.append([
                'runner', image, info['image_id'], info['repo_digest'],
                info['created'], info['architecture'], info['os'],
            ])
            binary_rows.append([
                benchmark, variant, image, canonical_image,
                probe['artifacts']['target']['path'],
                artifact_sha(probe, 'target'),
                probe['artifacts']['cmplog']['path'],
                artifact_sha(probe, 'cmplog'),
                probe['artifacts']['afl_fuzz']['path'],
                artifact_sha(probe, 'afl_fuzz'), dictionary_digest, seed_digest,
            ])
            argv_rows.append([
                benchmark, variant, image, probe['target_actual'] or
                probe['target_arg'], json.dumps(probe['afl_argv']),
                json.dumps(probe['cmplog_argv']),
                json.dumps([
                    use['argv_path'] for use in probe['dictionary_usage']
                ]),
            ])
            for key, value in probe['runtime_env'].items():
                env_rows.append([benchmark, variant, key, value])
            for use in probe['dictionary_usage']:
                dictionary_usage_rows.append([
                    benchmark, variant, use['argv_index'], use['argv_path'],
                    use['resolved_path'], use['root_path'], use['root_label'],
                    use['kind'], len(use['entries']),
                ])
                for file_order, item in enumerate(use['entries']):
                    dictionary_raw_rows.append([
                        benchmark, variant, use['argv_index'], file_order,
                        item['absolute_path'], item['mode'], item['size'],
                        item['mtime_ns'], item['content_sha256'],
                    ])
                    for token in item['token_multiset']:
                        token_multiset_rows.append([
                            benchmark, variant, use['argv_index'], file_order,
                            item['content_sha256'], token['token_b64'],
                            token['token_sha256'], token['multiplicity'],
                        ])
                        token_set_rows.append([
                            benchmark, variant, use['argv_index'], file_order,
                            item['content_sha256'], token['token_b64'],
                            token['token_sha256'],
                        ])
            if not probe['seed_manifest']:
                corpus_rows.append([
                    benchmark, variant, seed_digest, '', 0, 'NO_SEED_FILES'
                ])
            for seed in probe['seed_manifest']:
                corpus_rows.append([
                    benchmark, variant, seed_digest, seed['relative_path'],
                    seed['size'], seed['sha256'],
                ])

    for variant in VARIANTS:
        samples = [runner_probes[(benchmark, variant)] for benchmark in BENCHMARKS]
        cmplog_flags = [sample['cmplog_argv'] for sample in samples]
        env_matches = [
            all(sample['runtime_env'].get(key) == value
                for key, value in config[variant]['env'].items())
            for sample in samples
        ]
        variant_rows.append([
            variant, str(config[variant]['use_cmplog']).lower(),
            json.dumps(cmplog_flags), json.dumps(config[variant]['env'],
                                                  sort_keys=True),
            str(all(env_matches)).lower(),
            sha256_file(repo / 'fuzzers' / variant / 'runner.Dockerfile'),
        ])

    write_tsv(output / 'runtime_image_manifest.tsv', [
        'role', 'image', 'image_id', 'repo_digest', 'created', 'architecture',
        'os'
    ], runtime_rows)
    write_tsv(output / 'canonical_builder_manifest.tsv', [
        'benchmark', 'canonical_builder_image', 'target_binary_sha256',
        'cmplog_binary_sha256', 'afl_fuzz_binary_sha256',
        'dictionary_raw_signature_sha256', 'corpus_manifest_sha256'
    ], canonical_rows)
    write_tsv(output / 'canonical_artifact_file_manifest.tsv', [
        'benchmark', 'canonical_builder_image', 'absolute_path',
        'relative_path', 'size', 'sha256'
    ], canonical_file_rows)
    write_tsv(output / 'binary_hash_matrix.tsv', [
        'benchmark', 'fuzzer', 'runner_image', 'canonical_builder_image',
        'target_path', 'target_binary_sha256', 'cmplog_path',
        'cmplog_binary_sha256', 'afl_fuzz_path', 'afl_fuzz_binary_sha256',
        'dictionary_raw_signature_sha256', 'initial_corpus_manifest_sha256'
    ], binary_rows)
    write_tsv(output / 'dictionary_actual_usage.tsv', [
        'benchmark', 'fuzzer', 'x_argv_index', 'x_argv_path', 'resolved_path',
        'dictionary_root', 'root_label', 'kind', 'file_count'
    ], dictionary_usage_rows)
    write_tsv(output / 'dictionary_raw_manifest.tsv', [
        'benchmark', 'fuzzer', 'x_argv_index', 'file_order', 'absolute_path',
        'mode', 'size', 'mtime_ns', 'content_sha256'
    ], dictionary_raw_rows)
    write_tsv(output / 'dictionary_token_multiset.tsv', [
        'benchmark', 'fuzzer', 'x_argv_index', 'file_order',
        'raw_dictionary_sha256', 'token_b64', 'token_sha256', 'multiplicity'
    ], token_multiset_rows)
    write_tsv(output / 'dictionary_token_set.tsv', [
        'benchmark', 'fuzzer', 'x_argv_index', 'file_order',
        'raw_dictionary_sha256', 'token_b64', 'token_sha256'
    ], token_set_rows)
    write_tsv(output / 'corpus_manifest.tsv', [
        'benchmark', 'fuzzer', 'initial_corpus_manifest_sha256',
        'relative_path', 'size', 'sha256'
    ], corpus_rows)
    write_tsv(output / 'exact_argv.tsv', [
        'benchmark', 'fuzzer', 'runner_image', 'actual_target_path',
        'exact_afl_argv_json', 'actual_cmplog_argv_json',
        'actual_x_argv_paths_json'
    ], argv_rows)
    write_tsv(output / 'exact_env.tsv',
              ['benchmark', 'fuzzer', 'environment_variable', 'value'],
              env_rows)
    write_tsv(output / 'variant_configuration_matrix.tsv', [
        'variant', 'use_cmplog_expected', 'actual_cmplog_argv_by_benchmark',
        'configured_variant_env_json', 'runtime_env_matches_expected',
        'runner_dockerfile_sha256'
    ], variant_rows)


def write_build_summary(output: Path, records: list[BuildRecord]) -> None:
    ordered = sorted(records,
                     key=lambda row: (row.stage, row.benchmark, row.variant))
    write_tsv(output / 'build_summary.tsv', [
        'stage', 'benchmark', 'fuzzer', 'image', 'start_time', 'end_time',
        'duration_sec', 'attempts', 'exit_code', 'status', 'log_path'
    ], [[
        row.stage, row.benchmark, row.variant, row.image, row.start_time,
        row.end_time, row.duration_sec, row.attempts, row.exit_code, row.status,
        row.log_path
    ] for row in ordered])


def write_sha256s(output: Path) -> None:
    entries = []
    for path in sorted(output.rglob('*')):
        if not path.is_file() or path.name == 'SHA256SUMS':
            continue
        entries.append(f'{sha256_file(path)}  {path.relative_to(output)}')
    (output / 'SHA256SUMS').write_text('\n'.join(entries) + '\n',
                                       encoding='utf-8')


def write_report(output: Path, preflight: dict[str, Any],
                 gate: dict[str, Any], reuse_ok: bool,
                 legacy_ok: bool, runner_build_ok: bool) -> str:
    ready = (gate['status'] == 'PASS' and reuse_ok and legacy_ok and
             runner_build_ok)
    status = 'READY_FOR_BATCH_B_SMOKE' if ready else 'PROVENANCE_REPAIR_FAILED'
    lines = [
        '# Post-canonicalization provenance audit',
        '',
        f'final_status={status}',
        f'fuzzbench_commit={preflight["fuzzbench_commit"]}',
        f'aflplusplus_commit={preflight["aflplusplus_commit"]}',
        f'canonical_build_fuzzer={CANONICAL_BUILD_FUZZER}',
        f'runner_build_30_of_30_pass={str(runner_build_ok).lower()}',
        f'reused_control_and_coverage_validated={str(reuse_ok).lower()}',
        f'legacy_failed_runner_tags_preserved={str(legacy_ok).lower()}',
        f'provenance_gate={gate["status"]}',
        'smoke_started=false',
        'formal_started=false',
        'codex_monitor_started=false',
        '',
        'Canonical builders were built under new tags and are the only /out/ '
        'source for the thirty new runner tags.',
        'Dictionary records come exclusively from the actual captured -x argv '
        'paths. Raw bytes, token multiset, and unique token set are reported '
        'without rewriting or deduplicating any dictionary file.',
        '',
    ]
    if gate['failures']:
        lines.extend(['## Gate failures', ''])
        lines.extend(f'- {failure}' for failure in gate['failures'])
        lines.append('')
    else:
        lines.extend([
            'All five benchmarks have one raw target, CmpLog, afl-fuzz, '
            'dictionary, and initial-corpus artifact set across six runners.',
            '',
        ])
    (output / 'POST_CANONICALIZATION_PROVENANCE_AUDIT.md').write_text(
        '\n'.join(lines), encoding='utf-8')
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--results-root', type=Path, required=True)
    parser.add_argument('--reuse-evidence', type=Path, required=True)
    parser.add_argument('--aflplusplus-dir', type=Path, required=True)
    parser.add_argument('--namespace',
                        default='gcr.io/fuzzbench-batchb-focused')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--expected-parent', default=EXPECTED_PARENT)
    parser.add_argument('--plan-only', action='store_true')
    args = parser.parse_args()

    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]*', args.run_id):
        raise GateError(f'invalid run id: {args.run_id!r}')
    repo = args.repo.resolve()
    output = (args.results_root / f'canonicalization_{args.run_id}').resolve()
    if output.exists():
        raise GateError(f'refusing to overwrite existing evidence: {output}')
    output.mkdir(parents=True)
    logs_dir = output / 'logs'
    raw_dir = output / 'runtime_usage_raw'
    canonical_raw_dir = output / 'canonical_usage_raw'
    logs_dir.mkdir()
    raw_dir.mkdir()
    canonical_raw_dir.mkdir()

    if git_output(repo, 'status', '--porcelain'):
        raise GateError('FuzzBench worktree is not clean before the build')
    fuzzbench_commit = git_output(repo, 'rev-parse', 'HEAD')
    parent = git_output(repo, 'rev-parse', 'HEAD^')
    if parent != args.expected_parent:
        raise GateError(
            f'expected parent {args.expected_parent}, found {parent}')
    changed_paths = validate_changed_paths(repo, parent, fuzzbench_commit)
    preflight = {
        'fuzzbench_commit': fuzzbench_commit,
        'fuzzbench_parent': parent,
        'aflplusplus_commit': git_output(args.aflplusplus_dir.resolve(),
                                         'rev-parse', 'HEAD'),
        'changed_paths': changed_paths,
        'canonical_build_equivalence': validate_batchb_build_equivalence(repo),
        'runner_concurrency': RUNNER_CONCURRENCY,
        'transient_retry_attempts_max': MAX_TRANSIENT_ATTEMPTS,
        'legacy_images_are_not_build_inputs': True,
        'coverage_control_reuse_scope': {
            'new_helper_path_excluded_from_worker_context':
            'experiment/batch_b/',
            'base_image_copy_input': 'requirements.txt only',
            'coverage_copy_input':
            'benchmarks, fuzzers, common, experiment/runner.py',
        },
    }
    write_json(output / 'preflight.json', preflight)

    plan = build_plan(repo, args.namespace, args.run_id)
    write_json(output / 'build_plan.json', [{
        'stage': spec.stage,
        'benchmark': spec.benchmark,
        'variant': spec.variant,
        'image': spec.image,
        'dockerfile': str(spec.dockerfile),
        'context': str(spec.context),
        'build_args': dict(spec.build_args),
    } for spec in plan])
    if args.plan_only:
        print(output)
        return 0

    reuse_before = collect_reuse_before(args.namespace, repo)
    legacy_before = legacy_snapshot(args.namespace, repo)
    command_log = CommandLog(output / 'build_commands.jsonl')
    records = execute_builds(plan, repo, logs_dir, command_log)
    write_build_summary(output, records)
    runner_records = [record for record in records if record.stage == 'runner']
    runner_build_ok = (len(runner_records) == len(BENCHMARKS) * len(VARIANTS)
                       and all(record.status == 'PASS'
                               for record in runner_records))
    all_builds_ok = (len(records) == len(plan) and
                     all(record.status == 'PASS' for record in records))
    reuse_rows, reuse_ok = validate_reused_images(args.namespace, repo,
                                                   args.reuse_evidence,
                                                   reuse_before)
    write_tsv(output / 'reused_image_validation.tsv', [
        'role', 'image', 'frozen_image_id', 'before_image_id',
        'after_image_id', 'frozen_id_match', 'unchanged_during_run', 'status'
    ], [[
        row['role'], row['image'], row['frozen_image_id'],
        row['before_image_id'], row['after_image_id'],
        row['frozen_id_match'], row['unchanged_during_run'], row['status']
    ] for row in reuse_rows])
    legacy_after = legacy_snapshot(args.namespace, repo)
    legacy_rows = []
    legacy_ok = True
    for before, after in zip(legacy_before, legacy_after, strict=True):
        stable = (before['image_id'] != 'MISSING' and
                  before['image_id'] == after['image_id'])
        legacy_ok = legacy_ok and stable
        legacy_rows.append([
            before['image'], before['image_id'], after['image_id'],
            str(stable).lower(), 'PASS' if stable else 'FAIL'
        ])
    write_tsv(output / 'legacy_runner_tag_preservation.tsv', [
        'legacy_runner_image', 'before_image_id', 'after_image_id',
        'unchanged', 'status'
    ], legacy_rows)

    if not all_builds_ok:
        gate = {
            'status': 'FAIL',
            'failures': ['one or more canonical build stages failed'],
            'benchmarks': {},
        }
        status = write_report(output, preflight, gate, reuse_ok, legacy_ok,
                              runner_build_ok)
        write_json(output / 'provenance_gate.json', {
            'final_status': status,
            'builds_passed': all_builds_ok,
            'runner_build_30_of_30_pass': runner_build_ok,
            'reuse_validation_passed': reuse_ok,
            'legacy_tags_preserved': legacy_ok,
        })
        write_sha256s(output)
        print(output)
        return 1

    config = expected_variant_config(repo)
    canonical_probes: dict[str, dict[str, Any]] = {}
    runner_probes: dict[tuple[str, str], dict[str, Any]] = {}
    for benchmark in BENCHMARKS:
        target_name = read_yaml_scalar(
            repo / 'benchmarks' / benchmark / 'benchmark.yaml', 'fuzz_target')
        canonical = canonical_builder_image(args.namespace, args.run_id,
                                            benchmark)
        canonical_probe = run_artifact_probe(repo, canonical, target_name)
        canonical_probes[benchmark] = canonical_probe
        write_json(canonical_raw_dir / f'{benchmark}.json', canonical_probe)
        for variant in VARIANTS:
            image = canonical_runner_image(args.namespace, args.run_id,
                                           variant, benchmark)
            probe = run_probe(repo, image, variant, target_name)
            runner_probes[(benchmark, variant)] = probe
            write_json(raw_dir / f'{benchmark}__{variant}.json', probe)

    write_audit_tables(output, repo, args.namespace, args.run_id, canonical_probes,
                       runner_probes, config)
    gate = evaluate_gates(canonical_probes, runner_probes, config)
    status = write_report(output, preflight, gate, reuse_ok, legacy_ok,
                          runner_build_ok)
    write_json(output / 'provenance_gate.json', {
        'final_status': status,
        'runner_build_30_of_30_pass': runner_build_ok,
        'reuse_validation_passed': reuse_ok,
        'legacy_tags_preserved': legacy_ok,
        'gate': gate,
    })
    write_sha256s(output)
    print(output)
    return 0 if status == 'READY_FOR_BATCH_B_SMOKE' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except GateError as error:
        print(f'canonicalization gate error: {error}', file=sys.stderr)
        raise SystemExit(2)
