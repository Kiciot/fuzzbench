#!/usr/bin/env python3
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Runs fuzzer for trial."""

import glob
import importlib
import json
import os
import posixpath
import shlex
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import zipfile

from common import benchmark_config
from common import environment
from common import experiment_utils
from common import filesystem
from common import filestore_utils
from common import fuzzer_utils
from common import fuzzer_stats
from common import logs
from common import new_process
from common import retry
from common import sanitizer
from common import utils

NUM_RETRIES = 3
RETRY_DELAY = 3

FUZZ_TARGET_DIR = os.getenv('OUT', '/out')

CORPUS_ELEMENT_BYTES_LIMIT = 1 * 1024 * 1024
SEED_CORPUS_ARCHIVE_SUFFIX = '_seed_corpus.zip'

fuzzer_errored_out = False  # pylint:disable=invalid-name

CORPUS_DIRNAME = 'corpus'
RESULTS_DIRNAME = 'results'
CORPUS_ARCHIVE_DIRNAME = 'corpus-archives'


def _looks_like_afl_dir(d):
    """Checks if directory d looks like a valid AFL++ output dir.
    
    Returns True if:
    1. It has a 'queue' subdir AND
    2. It has strong AFL markers (fuzzer_stats, etc) OR 'queue' has regular files.
    """
    if not os.path.isdir(d):
        return False
    
    queue_dir = os.path.join(d, 'queue')
    if not os.path.isdir(queue_dir):
        return False

    # Strong indicators that this is the active output directory
    markers = ('fuzzer_stats', 'plot_data', 'cmdline', 'target_hash')
    if any(os.path.exists(os.path.join(d, m)) for m in markers):
        return True

    # Fallback: Check if queue has at least one VALID file (not dotfile, not subdir)
    try:
        with os.scandir(queue_dir) as it:
            for entry in it:
                if entry.is_file(follow_symlinks=False) and not entry.name.startswith('.'):
                    return True
    except OSError:
        pass
        
    return False


def _find_real_output_corpus_dir(output_corpus_dir):
    """Return the directory where AFL/AFL++ actually writes queue/ etc."""
    if not output_corpus_dir:
        return output_corpus_dir
    
    # Normalize path to avoid relative path/symlink confusion
    output_corpus_dir = os.path.abspath(output_corpus_dir)

    # 1. Check AFL++ common layouts (default/main/master) with strong validation
    for name in ('default', 'main', 'master'):
        cand = os.path.join(output_corpus_dir, name)
        if _looks_like_afl_dir(cand):
            return cand

    # 2. Check Legacy AFL layout: queue directly under output_corpus_dir
    if _looks_like_afl_dir(output_corpus_dir):
        return output_corpus_dir

    # 3. Fallback: search any child dir that looks like an AFL dir
    for cand in sorted(glob.glob(os.path.join(output_corpus_dir, '*'))):
        cand = os.path.abspath(cand)
        if _looks_like_afl_dir(cand):
            return cand

    # 4. Nothing found: keep original path
    return output_corpus_dir


def _clean_seed_corpus(seed_corpus_dir):
    """Prepares |seed_corpus_dir| for the trial."""
    if not os.path.exists(seed_corpus_dir):
        return

    if environment.get('NO_SEEDS'):
        logs.info('NO_SEEDS specified, deleting seed corpus files.')
        shutil.rmtree(seed_corpus_dir)
        os.mkdir(seed_corpus_dir)
        return

    failed_to_move_files = []
    for root, _, files in os.walk(seed_corpus_dir):
        for filename in files:
            file_path = os.path.join(root, filename)

            if os.path.getsize(file_path) > CORPUS_ELEMENT_BYTES_LIMIT:
                os.remove(file_path)
                logs.warning('Removed seed file %s as it exceeds 1 Mb limit.',
                             file_path)
                continue

            sha1sum = utils.file_hash(file_path)
            new_file_path = os.path.join(seed_corpus_dir, sha1sum)
            try:
                shutil.move(file_path, new_file_path)
            except OSError:
                failed_to_move_files.append((file_path, new_file_path))

    if failed_to_move_files:
        logs.error('Failed to move seed corpus files: %s', failed_to_move_files)


def get_clusterfuzz_seed_corpus_path(fuzz_target_path):
    """Returns the path of the clusterfuzz seed corpus archive if one exists."""
    if not fuzz_target_path:
        return None
    fuzz_target_without_extension = os.path.splitext(fuzz_target_path)[0]
    seed_corpus_path = (fuzz_target_without_extension +
                        SEED_CORPUS_ARCHIVE_SUFFIX)
    return seed_corpus_path if os.path.exists(seed_corpus_path) else None


def _unpack_random_corpus(corpus_directory):
    shutil.rmtree(corpus_directory)

    benchmark = environment.get('BENCHMARK')
    trial_group_num = environment.get('TRIAL_GROUP_NUM', 0)
    random_corpora_dir = experiment_utils.get_random_corpora_filestore_path()
    random_corpora_sub_dir = f'trial-group-{int(trial_group_num)}'
    random_corpus_dir = posixpath.join(random_corpora_dir, benchmark,
                                       random_corpora_sub_dir)
    filestore_utils.cp(random_corpus_dir, corpus_directory, recursive=True)


def _copy_custom_seed_corpus(corpus_directory):
    """Copy custom seed corpus provided by user"""
    shutil.rmtree(corpus_directory)
    benchmark = environment.get('BENCHMARK')
    benchmark_custom_corpus_dir = posixpath.join(
        experiment_utils.get_custom_seed_corpora_filestore_path(), benchmark)
    filestore_utils.cp(benchmark_custom_corpus_dir,
                       corpus_directory,
                       recursive=True)


def _unpack_clusterfuzz_seed_corpus(fuzz_target_path, corpus_directory):
    """If a clusterfuzz seed corpus archive is available, unpack it into the
    corpus directory."""
    oss_fuzz_corpus = environment.get('OSS_FUZZ_CORPUS')
    if oss_fuzz_corpus:
        benchmark = environment.get('BENCHMARK')
        corpus_archive_filename = f'{benchmark}.zip'
        oss_fuzz_corpus_archive_path = posixpath.join(
            experiment_utils.get_oss_fuzz_corpora_filestore_path(),
            corpus_archive_filename)
        seed_corpus_archive_path = posixpath.join(FUZZ_TARGET_DIR,
                                                  corpus_archive_filename)
        filestore_utils.cp(oss_fuzz_corpus_archive_path,
                           seed_corpus_archive_path)
    else:
        seed_corpus_archive_path = get_clusterfuzz_seed_corpus_path(
            fuzz_target_path)

    if not seed_corpus_archive_path:
        return

    with zipfile.ZipFile(seed_corpus_archive_path) as zip_file:
        idx = 0
        for zinfo in zip_file.infolist():
            if zinfo.is_dir():
                continue
            
            # Allow callers to opt-out of unpacking large files.
            if zinfo.file_size > CORPUS_ELEMENT_BYTES_LIMIT:
                continue

            output_filename = f'{idx:016d}'
            output_file_path = os.path.join(corpus_directory, output_filename)
            
            try:
                # Use open() + copyfileobj to ensure flat file creation
                with zip_file.open(zinfo) as src, open(output_file_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                idx += 1
            except Exception as e:
                # FIX A: Use standard logging formatting instead of f-string
                logs.warning('Failed to unpack seed %s: %s', zinfo.filename, e)

    logs.info('Unarchived %d files from seed corpus %s.', idx,
              seed_corpus_archive_path)


def run_fuzzer(max_total_time, log_filename):
    """Runs the fuzzer using its script."""
    input_corpus = environment.get('SEED_CORPUS_DIR')
    output_corpus = os.environ['OUTPUT_CORPUS_DIR']
    fuzz_target_name = environment.get('FUZZ_TARGET')
    target_binary = fuzzer_utils.get_fuzz_target_binary(FUZZ_TARGET_DIR,
                                                        fuzz_target_name)
    if not target_binary:
        logs.error('Fuzz target binary not found.')
        return

    if max_total_time is None:
        logs.warning('max_total_time is None. Fuzzing indefinitely.')

    runner_niceness = environment.get('RUNNER_NICENESS', 0)

    # Set sanitizer options environment variables if this is a bug based
    # benchmark.
    env = None
    benchmark = environment.get('BENCHMARK')
    if benchmark_config.get_config(benchmark).get('type') == 'bug':
        env = os.environ.copy()
        sanitizer.set_sanitizer_options(env, is_fuzz_run=True)

    try:
        command = [
            'nice', '-n',
            str(0 - runner_niceness), 'python3', '-u', '-c',
            (f'from fuzzers.{environment.get("FUZZER")} import fuzzer; '
             'fuzzer.fuzz('
             f'"{shlex.quote(input_corpus)}", "{shlex.quote(output_corpus)}", '
             f'"{shlex.quote(target_binary)}")')
        ]

        if environment.get('FUZZ_OUTSIDE_EXPERIMENT'):
            new_process.execute(command,
                                timeout=max_total_time,
                                write_to_stdout=True,
                                kill_children=True,
                                env=env)
        else:
            with open(log_filename, 'wb') as log_file:
                new_process.execute(command,
                                    timeout=max_total_time,
                                    output_file=log_file,
                                    kill_children=True,
                                    env=env)
    except subprocess.CalledProcessError:
        global fuzzer_errored_out  # pylint:disable=invalid-name
        fuzzer_errored_out = True
        logs.error('Fuzz process returned nonzero.')


class TrialRunner:  # pylint: disable=too-many-instance-attributes
    """Class for running a trial."""

    def __init__(self):
        self.fuzzer = environment.get('FUZZER')
        if not environment.get('FUZZ_OUTSIDE_EXPERIMENT'):
            benchmark = environment.get('BENCHMARK')
            trial_id = environment.get('TRIAL_ID')
            self.gcs_sync_dir = experiment_utils.get_trial_bucket_dir(
                self.fuzzer, benchmark, trial_id)
            filestore_utils.rm(self.gcs_sync_dir, force=True, parallel=True)
        else:
            self.gcs_sync_dir = None

        self.cycle = 0
        self.output_corpus = environment.get('OUTPUT_CORPUS_DIR')
        self.corpus_archives_dir = os.path.abspath(CORPUS_ARCHIVE_DIRNAME)
        self.results_dir = os.path.abspath(RESULTS_DIRNAME)
        self.log_file = os.path.join(self.results_dir, 'fuzzer-log.txt')
        self.last_sync_time = None
        self.last_archive_time = -float('inf')

    def initialize_directories(self):
        """Initialize directories needed for the trial."""
        directories = [
            self.output_corpus,
            self.corpus_archives_dir,
            self.results_dir,
        ]

        for directory in directories:
            filesystem.recreate_directory(directory)

    def set_up_corpus_directories(self):
        """Set up corpora for fuzzing."""
        fuzz_target_name = environment.get('FUZZ_TARGET')
        target_binary = fuzzer_utils.get_fuzz_target_binary(
            FUZZ_TARGET_DIR, fuzz_target_name)
        input_corpus = environment.get('SEED_CORPUS_DIR')
        os.makedirs(input_corpus, exist_ok=True)
        if environment.get('MICRO_EXPERIMENT'):
            _unpack_random_corpus(input_corpus)
        elif not environment.get('CUSTOM_SEED_CORPUS_DIR'):
            _unpack_clusterfuzz_seed_corpus(target_binary, input_corpus)
        else:
            _copy_custom_seed_corpus(input_corpus)

        _clean_seed_corpus(input_corpus)
        
        # Robust initialization using recreate_directory + copytree(dirs_exist_ok)
        filesystem.recreate_directory(self.output_corpus)
        try:
            shutil.copytree(input_corpus, self.output_corpus, dirs_exist_ok=True)
        except TypeError:
            # Fallback for older python where dirs_exist_ok is not supported
            shutil.rmtree(self.output_corpus)
            shutil.copytree(input_corpus, self.output_corpus)

    def conduct_trial(self):
        """Conduct the benchmarking trial."""
        self.initialize_directories()

        logs.info('Starting trial.')

        self.set_up_corpus_directories()

        max_total_time = environment.get('MAX_TOTAL_TIME')
        args = (max_total_time, self.log_file)

        # Sync initial corpus before fuzzing begins.
        self.do_sync()

        fuzz_thread = threading.Thread(target=run_fuzzer, args=args)
        fuzz_thread.start()
        if environment.get('FUZZ_OUTSIDE_EXPERIMENT'):
            time.sleep(5)

        while fuzz_thread.is_alive():
            self.cycle += 1
            self.sleep_until_next_sync()
            self.do_sync()

        logs.info('Doing final sync.')
        self.do_sync()
        fuzz_thread.join()

    def sleep_until_next_sync(self):
        """Sleep until it is time to do the next sync."""
        if self.last_sync_time is not None:
            next_sync_time = (self.last_sync_time +
                              experiment_utils.get_snapshot_seconds())
            sleep_time = next_sync_time - time.time()
            if sleep_time < 0:
                logs.warning('Sleep time on cycle %d is %d', self.cycle,
                             sleep_time)
                sleep_time = 0
        else:
            sleep_time = experiment_utils.get_snapshot_seconds()
        logs.debug('Sleeping for %d seconds.', sleep_time)
        time.sleep(sleep_time)
        self.last_sync_time = time.time()

    def do_sync(self):
        """Save corpus archives and results to GCS."""
        try:
            self.archive_and_save_corpus()
            # TODO(metzman): Enable stats.
            self.save_results()
            logs.debug('Finished sync.')
        except Exception:  # pylint: disable=broad-except
            logs.error('Failed to sync cycle: %d.', self.cycle)

    def record_stats(self):
        """Use fuzzer.get_stats if it is offered."""
        fuzzer_module = get_fuzzer_module(self.fuzzer)
        fuzzer_module_get_stats = getattr(fuzzer_module, 'get_stats', None)
        if fuzzer_module_get_stats is None:
            return

        try:
            output_corpus = environment.get('OUTPUT_CORPUS_DIR')
            real_output_corpus = _find_real_output_corpus_dir(output_corpus)
            stats_json_str = fuzzer_module_get_stats(real_output_corpus,
                                                     self.log_file)
        except Exception:  # pylint: disable=broad-except
            logs.error('Call to %s failed.', fuzzer_module_get_stats)
            return

        try:
            fuzzer_stats.validate_fuzzer_stats(stats_json_str)
        except (ValueError, json.decoder.JSONDecodeError):
            logs.error('Stats are invalid.')
            return

        stats_filename = experiment_utils.get_stats_filename(self.cycle)
        stats_path = os.path.join(self.results_dir, stats_filename)
        with open(stats_path, 'w', encoding='utf-8') as stats_file_handle:
            stats_file_handle.write(stats_json_str)

    def archive_corpus(self):
        """Archive this cycle's corpus."""
        archive = os.path.join(
            self.corpus_archives_dir,
            experiment_utils.get_corpus_archive_name(self.cycle))

        # Find the real corpus root with abspath and strict validation
        real_corpus_root = _find_real_output_corpus_dir(self.output_corpus)
        
        # Log warning if no queue found - debugging aid
        queue_dir = os.path.join(real_corpus_root, 'queue')
        if not os.path.isdir(queue_dir):
            logs.warning('No queue/ found in real_corpus_root=%s (cycle=%d). Archiving may be seed-only.',
                         real_corpus_root, self.cycle)

        with tarfile.open(archive, 'w:gz') as tar:
            new_archive_time = self.last_archive_time
            
            # FIX B: Use generator iteration (iter_targeted_corpus_elements)
            # to avoid building a huge list in memory.
            for file_path in iter_targeted_corpus_elements(real_corpus_root):
                try:
                    stat_info = os.stat(file_path)
                    last_modified_time = stat_info.st_mtime
                    if last_modified_time <= self.last_archive_time:
                        continue  # We've saved this file already.
                    new_archive_time = max(new_archive_time, last_modified_time)
                    
                    # Calculate arcname relative to the real root
                    arcname = os.path.relpath(file_path, real_corpus_root)
                    tar.add(file_path, arcname=arcname)
                    
                except (FileNotFoundError, OSError):
                    pass
                except Exception:  # pylint: disable=broad-except
                    logs.error('Unexpected exception occurred when archiving.')
        
        self.last_archive_time = new_archive_time
        return archive

    def save_corpus_archive(self, archive):
        """Save corpus |archive| to GCS and delete when done."""
        if not self.gcs_sync_dir:
            return

        basename = os.path.basename(archive)
        gcs_path = posixpath.join(self.gcs_sync_dir, CORPUS_DIRNAME, basename)

        filestore_utils.cp(archive, gcs_path)
        os.remove(archive)

    @retry.wrap(NUM_RETRIES, RETRY_DELAY,
                'experiment.runner.TrialRunner.archive_and_save_corpus')
    def archive_and_save_corpus(self):
        """Archive and save the current corpus to GCS."""
        archive = self.archive_corpus()
        self.save_corpus_archive(archive)

    @retry.wrap(NUM_RETRIES, RETRY_DELAY,
                'experiment.runner.TrialRunner.save_results')
    def save_results(self):
        """Save the results directory to GCS."""
        if not self.gcs_sync_dir:
            return
        results_copy = filesystem.make_dir_copy(self.results_dir)
        filestore_utils.rsync(
            results_copy, posixpath.join(self.gcs_sync_dir, RESULTS_DIRNAME))


def get_fuzzer_module(fuzzer):
    """Returns the fuzzer.py module for |fuzzer|."""
    fuzzer_module_name = f'fuzzers.{fuzzer}.fuzzer'
    fuzzer_module = importlib.import_module(fuzzer_module_name)
    return fuzzer_module


def iter_targeted_corpus_elements(corpus_dir):
    """Yields absolute paths to corpus elements in |corpus_dir|,
    filtering for specific subdirectories (queue, crashes, hangs).
    This avoids archiving unrelated stats/plot files.
    """
    corpus_dir = os.path.abspath(corpus_dir)
    # Only scan these directories
    target_subdirs = ['queue', 'crashes', 'hangs']
    
    for subdir in target_subdirs:
        target_path = os.path.join(corpus_dir, subdir)
        if not os.path.isdir(target_path):
            continue
            
        for root, _, files in os.walk(target_path):
            for filename in files:
                yield os.path.join(root, filename)


def get_corpus_elements(corpus_dir):
    """Returns a list of absolute paths to corpus elements in |corpus_dir|.
    Kept for compatibility if other modules import it, though unused here.
    """
    corpus_dir = os.path.abspath(corpus_dir)
    corpus_elements = []
    for root, _, files in os.walk(corpus_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            corpus_elements.append(file_path)
    return corpus_elements


def experiment_main():
    """Do a trial as part of an experiment."""
    logs.info('Doing trial as part of experiment.')
    try:
        runner = TrialRunner()
        runner.conduct_trial()
    except Exception as error:  # pylint: disable=broad-except
        logs.error('Error doing trial.')
        raise error


def main():
    """Do an experiment on a development machine or on a GCP runner instance."""
    logs.initialize(
        default_extras={
            'benchmark': environment.get('BENCHMARK'),
            'component': 'runner',
            'fuzzer': environment.get('FUZZER'),
            'trial_id': str(environment.get('TRIAL_ID')),
        })
    experiment_main()
    if fuzzer_errored_out:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())