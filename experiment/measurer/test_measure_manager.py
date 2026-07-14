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
"""Tests for measure_manager.py."""
import os
import shutil
from unittest import mock
import multiprocessing
import queue
import threading
import time

import pytest

from common import experiment_utils
from common import new_process
from database import models
from database import utils as db_utils
from experiment.build import build_utils
from experiment.measurer import measure_manager
from test_libs import utils as test_utils
import experiment.measurer.datatypes as measurer_datatypes

TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), 'test_data')

# Arbitrary values to use in tests.
FUZZER = 'fuzzer-a'
BENCHMARK = 'benchmark-a'
TRIAL_NUM = 12
FUZZERS = ['fuzzer-a', 'fuzzer-b']
BENCHMARKS = ['benchmark-1', 'benchmark-2']
NUM_TRIALS = 4
MAX_TOTAL_TIME = 100
GIT_HASH = 'FAKE-GIT-HASH'
CYCLE = 1

SNAPSHOT_LOGGER = measure_manager.logger
REGION_COVERAGE = False

# pylint: disable=unused-argument,invalid-name,redefined-outer-name,protected-access


@pytest.fixture
def db_experiment(experiment_config, db):
    """A fixture that populates the database with an experiment entity with the
    name specified in the experiment_config fixture."""
    experiment = models.Experiment(name=experiment_config['experiment'])
    db_utils.add_all([experiment])
    # yield so that the experiment exists until the using function exits.
    yield


def test_get_current_coverage(fs, experiment):
    """Tests that get_current_coverage reads the correct data from json file."""
    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    json_cov_summary_file = get_test_data_path('cov_summary.json')
    fs.add_real_file(json_cov_summary_file, read_only=False)
    snapshot_measurer.cov_summary_file = json_cov_summary_file
    covered_branches = snapshot_measurer.get_current_coverage()
    assert covered_branches == 7


def test_get_current_coverage_error(fs, experiment):
    """Tests that get_current_coverage returns None from a
    defective json file."""
    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    json_cov_summary_file = get_test_data_path('cov_summary_defective.json')
    fs.add_real_file(json_cov_summary_file, read_only=False)
    snapshot_measurer.cov_summary_file = json_cov_summary_file
    covered_branches = snapshot_measurer.get_current_coverage()
    assert not covered_branches


def test_get_current_coverage_no_file(fs, experiment):
    """Tests that get_current_coverage returns None with no json file."""
    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    json_cov_summary_file = get_test_data_path('cov_summary_not_exist.json')
    snapshot_measurer.cov_summary_file = json_cov_summary_file
    covered_branches = snapshot_measurer.get_current_coverage()
    assert not covered_branches


@mock.patch('common.new_process.execute')
def test_generate_profdata_create(mocked_execute, experiment, fs):
    """Tests that generate_profdata can run the correct command."""
    mocked_execute.return_value = new_process.ProcessResult(0, '', False)
    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    snapshot_measurer.profdata_file = '/work/reports/data.profdata'
    snapshot_measurer.profraw_file_pattern = '/work/reports/data-%m.profraw'
    profraw_file = '/work/reports/data-123.profraw'
    fs.create_file(profraw_file, contents='fake_contents')
    snapshot_measurer.generate_profdata(CYCLE)

    expected = [
        'llvm-profdata', 'merge', '-sparse', '/work/reports/data-123.profraw',
        '-o', '/work/reports/data.profdata'
    ]

    assert (len(mocked_execute.call_args_list)) == 1
    args = mocked_execute.call_args_list[0]
    assert args[0][0] == expected


@mock.patch('common.new_process.execute')
def test_generate_profdata_merge(mocked_execute, experiment, fs):
    """Tests that generate_profdata can run correctly with existing profraw."""
    mocked_execute.return_value = new_process.ProcessResult(0, '', False)
    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    snapshot_measurer.profdata_file = '/work/reports/data.profdata'
    snapshot_measurer.profraw_file_pattern = '/work/reports/data-%m.profraw'
    profraw_file = '/work/reports/data-123.profraw'
    fs.create_file(profraw_file, contents='fake_contents')
    fs.create_file(snapshot_measurer.profdata_file, contents='fake_contents')
    snapshot_measurer.generate_profdata(CYCLE)

    expected = [
        'llvm-profdata', 'merge', '-sparse', '/work/reports/data-123.profraw',
        '/work/reports/data.profdata', '-o', '/work/reports/data.profdata'
    ]

    assert (len(mocked_execute.call_args_list)) == 1
    args = mocked_execute.call_args_list[0]
    assert args[0][0] == expected


@mock.patch('common.new_process.execute')
@mock.patch('experiment.measurer.coverage_utils.get_coverage_binary')
def test_generate_summary(mocked_get_coverage_binary, mocked_execute,
                          experiment, fs):
    """Tests that generate_summary can run the correct command."""
    mocked_execute.return_value = new_process.ProcessResult(0, '', False)
    coverage_binary_path = '/work/coverage-binaries/benchmark-a/fuzz-target'
    mocked_get_coverage_binary.return_value = coverage_binary_path

    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    snapshot_measurer.cov_summary_file = '/reports/cov_summary.txt'
    snapshot_measurer.profdata_file = '/reports/data.profdata'
    fs.create_dir('/reports')
    fs.create_file(snapshot_measurer.profdata_file, contents='fake_contents')
    snapshot_measurer.generate_summary(CYCLE)

    expected = [
        'llvm-cov', 'export', '-format=text', '-num-threads=1',
        '-region-coverage-gt=0', '-skip-expansions',
        '/work/coverage-binaries/benchmark-a/fuzz-target',
        '-instr-profile=/reports/data.profdata'
    ]

    assert (len(mocked_execute.call_args_list)) == 1
    args = mocked_execute.call_args_list[0]
    assert args[0][0] == expected
    assert args[1]['output_file'].name == '/reports/cov_summary.txt'


@mock.patch('common.logs.error')
@mock.patch('experiment.measurer.measure_manager.initialize_logs')
@mock.patch('multiprocessing.Queue')
@mock.patch('experiment.measurer.measure_manager.measure_snapshot_coverage')
def test_measure_trial_coverage(mocked_measure_snapshot_coverage, mocked_queue,
                                _, __):
    """Tests that measure_trial_coverage works as expected."""
    min_cycle = 1
    max_cycle = 10
    measure_request = measurer_datatypes.SnapshotMeasureRequest(
        FUZZER, BENCHMARK, TRIAL_NUM, min_cycle)
    measure_manager.measure_trial_coverage(measure_request, max_cycle,
                                           mocked_queue(), False)
    expected_calls = [
        mock.call(FUZZER, BENCHMARK, TRIAL_NUM, cycle, False)
        for cycle in range(min_cycle, max_cycle + 1)
    ]
    assert mocked_measure_snapshot_coverage.call_args_list == expected_calls


@mock.patch('common.filestore_utils.ls')
@mock.patch('common.filestore_utils.rsync')
def test_measure_all_trials_not_ready(mocked_rsync, mocked_ls, experiment):
    """Test running measure_all_trials before it is ready works as intended."""
    mocked_ls.return_value = new_process.ProcessResult(1, '', False)
    assert measure_manager.measure_all_trials(
        experiment_utils.get_experiment_name(), MAX_TOTAL_TIME,
        test_utils.MockPool(), queue.Queue(), False)
    assert not mocked_rsync.called


@mock.patch('multiprocessing.pool.ThreadPool', test_utils.MockPool)
@mock.patch('common.new_process.execute')
@mock.patch('common.filesystem.directories_have_same_files')
@pytest.mark.skip(reason='See crbug.com/1012329')
def test_measure_all_trials_no_more(mocked_directories_have_same_files,
                                    mocked_execute):
    """Test measure_all_trials does what is intended when the experiment is
    done."""
    mocked_directories_have_same_files.return_value = True
    mocked_execute.return_value = new_process.ProcessResult(0, '', False)
    mock_pool = test_utils.MockPool()
    assert not measure_manager.measure_all_trials(
        experiment_utils.get_experiment_name(), MAX_TOTAL_TIME, mock_pool,
        queue.Queue(), False)


@mock.patch('common.new_process.execute')
@mock.patch('common.benchmark_utils.get_fuzz_target',
            return_value='fuzz-target')
def test_run_cov_new_units(_, mocked_execute, fs, environ):
    """Tests that run_cov_new_units does a coverage run as we expect."""
    os.environ = {
        'WORK': '/work',
        'EXPERIMENT_FILESTORE': 'gs://bucket',
        'EXPERIMENT': 'experiment',
    }
    mocked_execute.return_value = new_process.ProcessResult(0, '', False)
    snapshot_measurer = measure_manager.SnapshotMeasurer(
        FUZZER, BENCHMARK, TRIAL_NUM, SNAPSHOT_LOGGER, REGION_COVERAGE)
    snapshot_measurer.initialize_measurement_dirs()
    new_units = ['new1', 'new2']
    for unit in new_units:
        fs.create_file(os.path.join(snapshot_measurer.corpus_dir, unit))
    fuzz_target_path = '/work/coverage-binaries/benchmark-a/fuzz-target'
    fs.create_file(fuzz_target_path)
    profraw_file_path = os.path.join(snapshot_measurer.coverage_dir,
                                     'data.profraw')
    fs.create_file(profraw_file_path)

    snapshot_measurer.run_cov_new_units()
    assert len(mocked_execute.call_args_list) == 1  # Called once
    args = mocked_execute.call_args_list[0]
    command_arg = args[0][0]
    assert command_arg[0] == fuzz_target_path
    expected = {
        'cwd': '/work/coverage-binaries/benchmark-a',
        'env': {
            'ASAN_OPTIONS':
                ('alloc_dealloc_mismatch=0:allocator_may_return_null=1:'
                 'allocator_release_to_os_interval_ms=500:'
                 'allow_user_segv_handler=0:check_malloc_usable_size=0:'
                 'detect_leaks=1:detect_odr_violation=0:'
                 'detect_stack_use_after_return=1:fast_unwind_on_fatal=0:'
                 'handle_abort=2:handle_segv=2:handle_sigbus=2:handle_sigfpe=2:'
                 'handle_sigill=2:max_uar_stack_size_log=16:'
                 'quarantine_size_mb=64:strict_memcmp=1:symbolize=1:'
                 'symbolize_inline_frames=0'),
            'UBSAN_OPTIONS':
                ('allocator_release_to_os_interval_ms=500:handle_abort=2:'
                 'handle_segv=2:handle_sigbus=2:handle_sigfpe=2:'
                 'handle_sigill=2:print_stacktrace=1:'
                 'symbolize=1:symbolize_inline_frames=0'),
            'LLVM_PROFILE_FILE':
                ('/work/measurement-folders/'
                 'benchmark-a-fuzzer-a/trial-12/coverage/data-%m.profraw'),
            'WORK': '/work',
            'EXPERIMENT_FILESTORE': 'gs://bucket',
            'EXPERIMENT': 'experiment',
        },
        'expect_zero': False,
    }
    args = args[1]
    for arg, value in expected.items():
        assert args[arg] == value


def get_test_data_path(*subpaths):
    """Returns the path of |subpaths| relative to TEST_DATA_PATH."""
    return os.path.join(TEST_DATA_PATH, *subpaths)


class TestIntegrationMeasurement:
    """Integration tests for measurement."""

    # TODO(metzman): Get this test working everywhere by using docker or a more
    # portable binary.
    @pytest.mark.skipif(not os.getenv('FUZZBENCH_TEST_INTEGRATION'),
                        reason='Not running integration tests.')
    def test_measure_snapshot_coverage(  # pylint: disable=too-many-locals
            self, db, experiment, tmp_path):
        """Integration test for measure_snapshot_coverage."""
        # WORK is set by experiment to a directory that only makes sense in a
        # fakefs. A directory containing necessary llvm tools is also added to
        # PATH.
        llvm_tools_path = get_test_data_path('llvm_tools')
        os.environ['PATH'] += os.pathsep + llvm_tools_path
        os.environ['WORK'] = str(tmp_path)
        # Set up the coverage binary.
        benchmark = 'freetype2_ftfuzzer'
        coverage_binary_src = get_test_data_path(
            'test_measure_snapshot_coverage', benchmark + '-coverage')
        benchmark_cov_binary_dir = os.path.join(
            build_utils.get_coverage_binaries_dir(), benchmark)

        os.makedirs(benchmark_cov_binary_dir)
        coverage_binary_dst_dir = os.path.join(benchmark_cov_binary_dir,
                                               'ftfuzzer')

        shutil.copy(coverage_binary_src, coverage_binary_dst_dir)

        # Set up entities in database so that the snapshot can be created.
        experiment = models.Experiment(name=os.environ['EXPERIMENT'])
        db_utils.add_all([experiment])
        trial = models.Trial(fuzzer=FUZZER,
                             benchmark=benchmark,
                             experiment=os.environ['EXPERIMENT'])
        db_utils.add_all([trial])

        snapshot_measurer = measure_manager.SnapshotMeasurer(
            trial.fuzzer, trial.benchmark, trial.id, SNAPSHOT_LOGGER,
            REGION_COVERAGE)

        # Set up the snapshot archive.
        cycle = 1
        archive = get_test_data_path('test_measure_snapshot_coverage',
                                     f'corpus-archive-{cycle:04d}.tar.gz')
        corpus_dir = os.path.join(snapshot_measurer.trial_dir, 'corpus')
        os.makedirs(corpus_dir)
        shutil.copy(archive, corpus_dir)

        with mock.patch('common.filestore_utils.cp') as mocked_cp:
            mocked_cp.return_value = new_process.ProcessResult(0, '', False)
            # TODO(metzman): Create a system for using actual buckets in
            # integration tests.
            snapshot = measure_manager.measure_snapshot_coverage(
                snapshot_measurer.fuzzer, snapshot_measurer.benchmark,
                snapshot_measurer.trial_num, cycle, False)
        assert snapshot
        assert snapshot.time == cycle * experiment_utils.get_snapshot_seconds()
        assert snapshot.edges_covered == 4629


@pytest.mark.parametrize('archive_name',
                         ['libfuzzer-corpus.tgz', 'afl-corpus.tgz'])
def test_extract_corpus(archive_name, tmp_path):
    """"Tests that extract_corpus unpacks a corpus as we expect."""
    archive_path = get_test_data_path(archive_name)
    measure_manager.extract_corpus(archive_path, tmp_path)
    expected_corpus_files = {
        '5ea57dfc9631f35beecb5016c4f1366eb6faa810',
        '2f1507c3229c5a1f8b619a542a8e03ccdbb3c29c',
        'b6ccc20641188445fa30c8485a826a69ac4c6b60'
    }
    assert expected_corpus_files.issubset(set(os.listdir(tmp_path)))


@mock.patch('time.sleep', return_value=None)
@mock.patch('experiment.measurer.measure_manager.set_up_coverage_binaries')
@mock.patch('experiment.measurer.measure_manager.measure_all_trials',
            return_value=False)
@mock.patch('multiprocessing.Manager')
@mock.patch('multiprocessing.pool')
@mock.patch('experiment.scheduler.all_trials_ended', return_value=True)
def test_measure_loop_end(_, __, ___, ____, _____, ______, experiment_config,
                          db_experiment):
    """Tests that measure_loop stops when there is nothing left to measure. In
    this test, there is nothing left to measure on the first call."""
    measure_manager.measure_loop(experiment_config, 100)
    # If everything went well, we should get to this point without any
    # exceptions.


@mock.patch('time.sleep', return_value=None)
@mock.patch('experiment.measurer.measure_manager.set_up_coverage_binaries')
@mock.patch('multiprocessing.Manager')
@mock.patch('multiprocessing.pool')
@mock.patch('experiment.scheduler.all_trials_ended', return_value=True)
@mock.patch('experiment.measurer.measure_manager.measure_all_trials')
def test_measure_loop_loop_until_end(mocked_measure_all_trials, _, __, ___,
                                     ____, _____, experiment_config,
                                     db_experiment):
    """Test that measure loop will stop measuring when all trials have ended. In
    this test, there is more to measure for a few iterations, then the mocked
    functions will indicate that there is nothing left to measure."""
    call_count = 0
    # Scheduler is running.
    loop_iterations = 6

    def mock_measure_all_trials(*args, **kwargs):
        # Do the assertions here so that there will be an assert fail on failure
        # instead of an infinite loop.
        nonlocal call_count
        call_count += 1
        if call_count >= loop_iterations:
            return False
        return True

    mocked_measure_all_trials.side_effect = mock_measure_all_trials
    measure_manager.measure_loop(experiment_config, 100)
    assert call_count == loop_iterations


@mock.patch('common.new_process.execute')
def test_path_exists_in_experiment_filestore(mocked_execute, environ):
    """Tests that remote_dir_exists calls gsutil properly."""
    work_dir = '/work'
    os.environ['WORK'] = work_dir
    os.environ['EXPERIMENT_FILESTORE'] = 'gs://cloud-bucket'
    os.environ['EXPERIMENT'] = 'example-experiment'
    measure_manager.exists_in_experiment_filestore(work_dir)
    mocked_execute.assert_called_with(
        ['gsutil', 'ls', 'gs://cloud-bucket/example-experiment'],
        expect_zero=False)


def test_consume_unmapped_type_from_response_queue():
    """Tests the scenario where an unmapped type is retrieved from the response
    queue. This scenario is not expected to happen, so in this case no snapshots
    are returned."""
    # Use normal queue here as multiprocessing queue gives flaky tests.
    response_queue = queue.Queue()
    response_queue.put('unexpected string')
    snapshots = measure_manager.consume_snapshots_from_response_queue(
        response_queue, set())
    assert not snapshots


def test_consume_retry_type_from_response_queue():
    """Tests the scenario where a retry object is retrieved from the
    response queue. In this scenario, we want to remove the snapshot identifier
    from the queued_snapshots set, as this allows the measurement task to be
    retried in the future."""
    # Use normal queue here as multiprocessing queue gives flaky tests.
    response_queue = queue.Queue()
    retry_request_object = measurer_datatypes.RetryRequest(
        'fuzzer', 'benchmark', TRIAL_NUM, CYCLE)
    snapshot_identifier = (TRIAL_NUM, CYCLE)
    response_queue.put(retry_request_object)
    queued_snapshots_set = set([snapshot_identifier])
    snapshots = measure_manager.consume_snapshots_from_response_queue(
        response_queue, queued_snapshots_set)
    assert not snapshots
    assert len(queued_snapshots_set) == 0


def test_consume_snapshot_type_from_response_queue():
    """Tests the scenario where a measured snapshot is retrieved from the
    response queue. In this scenario, we want to return the snapshot in the
    function."""
    # Use normal queue here as multiprocessing queue gives flaky tests.
    response_queue = queue.Queue()
    snapshot_identifier = (TRIAL_NUM, CYCLE)
    queued_snapshots_set = set([snapshot_identifier])
    measured_snapshot = models.Snapshot(
        trial_id=TRIAL_NUM,
        time=experiment_utils.get_cycle_time(CYCLE),
        edges_covered=1)
    response_queue.put(measured_snapshot)
    assert response_queue.qsize() == 1
    snapshots = measure_manager.consume_snapshots_from_response_queue(
        response_queue, queued_snapshots_set)
    assert len(snapshots) == 1


@mock.patch('experiment.measurer.measure_manager.get_unmeasured_snapshots')
def test_measure_manager_inner_loop_break_condition(
        mocked_get_unmeasured_snapshots):
    """Tests that the measure manager inner loop returns False when there's no
    more snapshots left to be measured."""
    # Empty list means no more snapshots left to be measured.
    mocked_get_unmeasured_snapshots.return_value = []
    request_queue = queue.Queue()
    response_queue = queue.Queue()
    continue_inner_loop = measure_manager.measure_manager_inner_loop(
        'experiment', 1, request_queue, response_queue, set())
    assert not continue_inner_loop


@mock.patch('experiment.measurer.measure_manager._corpus_archive_exists',
            return_value=True)
@mock.patch('experiment.measurer.measure_manager.get_unmeasured_snapshots')
@mock.patch(
    'experiment.measurer.measure_manager.consume_snapshots_from_response_queue')
def test_measure_manager_inner_loop_writes_to_request_queue(
        mocked_consume_snapshots_from_response_queue,
        mocked_get_unmeasured_snapshots, _):
    """Tests that the measure manager inner loop is writing measurement tasks to
    request queue."""
    mocked_get_unmeasured_snapshots.return_value = [
        measurer_datatypes.SnapshotMeasureRequest('fuzzer', 'benchmark', 0, 0)
    ]
    mocked_consume_snapshots_from_response_queue.return_value = []
    request_queue = queue.Queue()
    response_queue = queue.Queue()
    measure_manager.measure_manager_inner_loop('experiment', 1, request_queue,
                                               response_queue, set())
    assert request_queue.qsize() == 1


@mock.patch('experiment.measurer.measure_manager._corpus_archive_exists',
            return_value=True)
@mock.patch('experiment.measurer.measure_manager.get_unmeasured_snapshots')
@mock.patch(
    'experiment.measurer.measure_manager.consume_snapshots_from_response_queue')
@mock.patch('database.utils.add_all')
def test_measure_manager_inner_loop_dont_write_to_db(
        mocked_add_all, mocked_consume_snapshots_from_response_queue,
        mocked_get_unmeasured_snapshots, _):
    """Tests that the measure manager inner loop does not call add_all to write
    to the database, when there are no measured snapshots to be written."""
    mocked_get_unmeasured_snapshots.return_value = [
        measurer_datatypes.SnapshotMeasureRequest('fuzzer', 'benchmark', 0, 0)
    ]
    request_queue = queue.Queue()
    response_queue = queue.Queue()
    mocked_consume_snapshots_from_response_queue.return_value = []
    measure_manager.measure_manager_inner_loop('experiment', 1, request_queue,
                                               response_queue, set())
    mocked_add_all.not_called()


@mock.patch('experiment.measurer.measure_manager._corpus_archive_exists',
            return_value=True)
@mock.patch('experiment.measurer.measure_manager.get_unmeasured_snapshots')
@mock.patch(
    'experiment.measurer.measure_manager.consume_snapshots_from_response_queue')
@mock.patch('database.utils.add_all')
def test_measure_manager_inner_loop_writes_to_db(
        mocked_add_all, mocked_consume_snapshots_from_response_queue,
        mocked_get_unmeasured_snapshots, _):
    """Tests that the measure manager inner loop calls add_all to write
    to the database, when there are measured snapshots to be written."""
    mocked_get_unmeasured_snapshots.return_value = [
        measurer_datatypes.SnapshotMeasureRequest('fuzzer', 'benchmark', 0, 0)
    ]
    request_queue = queue.Queue()
    response_queue = queue.Queue()
    snapshot_model = models.Snapshot(trial_id=1)
    mocked_consume_snapshots_from_response_queue.return_value = [snapshot_model]
    measure_manager.measure_manager_inner_loop('experiment', 1, request_queue,
                                               response_queue, set())
    mocked_add_all.assert_called_with([snapshot_model])


def _request(trial_id, cycle=1):
    return measurer_datatypes.SnapshotMeasureRequest(
        FUZZER, BENCHMARK, trial_id, cycle)


def _snapshot(trial_id, cycle=1):
    return models.Snapshot(
        trial_id=trial_id,
        time=experiment_utils.get_cycle_time(cycle),
        edges_covered=trial_id)


def _fake_terminal_flush(monkeypatch, requests, delayed_snapshots,
                         timeout=1):
    """Run the terminal state machine with deterministic in-memory queues."""
    expected = {(request.trial_id, request.cycle) for request in requests}
    persisted = set()
    lifecycle = measure_manager.MeasurementLifecycle()
    queued = set(expected)
    for request in requests:
        lifecycle.record_submission(request)
    response_queue = queue.Queue()

    monkeypatch.setattr(measure_manager, 'get_expected_terminal_measurements',
                        lambda _experiment, _cycle: expected)
    monkeypatch.setattr(measure_manager, 'get_persisted_terminal_measurements',
                        lambda _experiment, _cycle: set(persisted))
    monkeypatch.setattr(measure_manager, 'get_unmeasured_snapshots',
                        lambda _experiment, _cycle: [])

    def persist(_experiment, snapshots, state):
        identifiers = {
            state.snapshot_identifier(snapshot) for snapshot in snapshots
        }
        persisted.update(identifiers)
        state.record_persisted(identifiers)
        return len(identifiers)

    monkeypatch.setattr(measure_manager, 'persist_snapshots_exactly_once',
                        persist)

    def publish():
        time.sleep(0.02)
        for snapshot in delayed_snapshots:
            response_queue.put(snapshot)

    publisher = threading.Thread(target=publish)
    publisher.start()
    diagnostics = measure_manager.drain_terminal_measurements(
        'experiment', 1, queue.Queue(), response_queue, queued, lifecycle,
        timeout, 0.001)
    publisher.join()
    return diagnostics, lifecycle


def test_measurer_drains_delayed_terminal_responses(monkeypatch):
    """Ten delayed final responses are persisted after trials have ended."""
    requests = [_request(trial_id) for trial_id in range(1, 11)]
    diagnostics, lifecycle = _fake_terminal_flush(
        monkeypatch, requests,
        [_snapshot(trial_id) for trial_id in range(1, 11)])
    assert diagnostics['measurement_requests_submitted'] == 10
    assert diagnostics['measurement_responses_received'] == 10
    assert diagnostics['measurement_rows_persisted'] == 10
    assert diagnostics['measurement_requests_in_flight'] == 0
    assert diagnostics['persisted_terminal_measurements'] == 10
    assert lifecycle.successful_counts_match()


def test_all_trials_ended_does_not_drop_inflight_measurements(monkeypatch):
    """An in-flight response remains required after all_trials_ended."""
    request = _request(1)
    diagnostics, lifecycle = _fake_terminal_flush(
        monkeypatch, [request], [_snapshot(1)])
    assert diagnostics['missing_terminal_measurements'] == []
    assert not lifecycle.in_flight
    assert lifecycle.submitted == lifecycle.received == lifecycle.persisted


def test_terminal_measurements_persist_exactly_once(db_experiment,
                                                    experiment_config):
    """Duplicate responses produce one row under the composite DB key."""
    trial = models.Trial(
        id=TRIAL_NUM,
        experiment=experiment_config['experiment'],
        fuzzer=FUZZER,
        benchmark=BENCHMARK,
        time_started=measure_manager.scheduler.datetime_now(),
        time_ended=measure_manager.scheduler.datetime_now())
    db_utils.add_all([trial])
    lifecycle = measure_manager.MeasurementLifecycle()
    request = _request(TRIAL_NUM)
    lifecycle.record_submission(request)
    response_queue = queue.Queue()
    response_queue.put(_snapshot(TRIAL_NUM))
    response_queue.put(_snapshot(TRIAL_NUM))
    snapshots = measure_manager.consume_snapshots_from_response_queue(
        response_queue, {(TRIAL_NUM, CYCLE)}, lifecycle)
    assert len(snapshots) == 1
    assert measure_manager.persist_snapshots_exactly_once(
        experiment_config['experiment'], snapshots, lifecycle) == 1
    with db_utils.session_scope() as session:
        rows = session.query(models.Snapshot).filter_by(
            trial_id=TRIAL_NUM,
            time=experiment_utils.get_cycle_time(CYCLE)).all()
    assert len(rows) == 1
    assert lifecycle.duplicate_responses == 1
    assert lifecycle.successful_counts_match()


def test_flush_timeout_reports_missing_campaigns(monkeypatch):
    """A bounded timeout fails with exact missing measurement diagnostics."""
    requests = [_request(trial_id) for trial_id in range(1, 11)]
    expected = {(request.trial_id, request.cycle) for request in requests}
    lifecycle = measure_manager.MeasurementLifecycle()
    for request in requests:
        lifecycle.record_submission(request)
    received = [_snapshot(trial_id) for trial_id in range(1, 10)]
    for snapshot in received:
        lifecycle.record_response(snapshot)
    persisted = {lifecycle.snapshot_identifier(snapshot) for snapshot in received}
    lifecycle.record_persisted(persisted)
    monkeypatch.setattr(measure_manager, 'get_expected_terminal_measurements',
                        lambda _experiment, _cycle: expected)
    monkeypatch.setattr(measure_manager, 'get_persisted_terminal_measurements',
                        lambda _experiment, _cycle: persisted)
    monkeypatch.setattr(measure_manager, 'get_unmeasured_snapshots',
                        lambda _experiment, _cycle: [])
    monkeypatch.setattr(measure_manager, '_describe_measurements',
                        lambda _experiment, identifiers: sorted(identifiers))
    with pytest.raises(measure_manager.TerminalResponseFlushError) as error:
        measure_manager.drain_terminal_measurements(
            'experiment', 1, queue.Queue(), queue.Queue(), {(10, 1)},
            lifecycle, 0.01, 0.001)
    message = str(error.value)
    assert '"measurement_requests_submitted": 10' in message
    assert '"measurement_responses_received": 9' in message
    assert '"measurement_rows_persisted": 9' in message
    assert '"missing_terminal_measurements": [[10, 1]]' in message


def test_measurer_workers_are_reaped():
    """Every worker acknowledges its sentinel and the pool joins cleanly."""
    manager = multiprocessing.Manager()
    request_queue = manager.Queue()
    response_queue = manager.Queue()
    worker = measure_manager.measure_worker.LocalMeasureWorker({
        'request_queue': request_queue,
        'response_queue': response_queue,
        'region_coverage': False,
    })
    pool = multiprocessing.Pool(processes=2)
    results = [pool.apply_async(worker.measure_worker_loop) for _ in range(2)]
    acknowledgements = measure_manager.shutdown_measurement_workers(
        'experiment', pool, results, 2, request_queue, response_queue, set(),
        measure_manager.MeasurementLifecycle(), 5)
    manager.shutdown()
    assert len(acknowledgements) == 2
    assert all(result.ready() and result.successful() for result in results)
    assert not [
        child for child in multiprocessing.active_children()
        if child.pid in acknowledgements
    ]
