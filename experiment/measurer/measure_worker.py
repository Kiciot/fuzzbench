# Copyright 2024 Google LLC
# ... (License header) ...
"""Module for measurer workers logic."""
import time
import traceback
from typing import Dict, Optional
from common import logs
from database.models import Snapshot
import experiment.measurer.datatypes as measurer_datatypes
from experiment.measurer import measure_manager

MEASUREMENT_TIMEOUT = 1
logger = logs.Logger()  # pylint: disable=invalid-name


class BaseMeasureWorker:
    """Base class for measure worker."""

    def __init__(self, config: Dict):
        self.request_queue = config['request_queue']
        self.response_queue = config['response_queue']
        self.region_coverage = config['region_coverage']

    def get_task_from_request_queue(self):
        raise NotImplementedError

    def put_result_in_response_queue(self, measured_snapshot, request):
        raise NotImplementedError

    def measure_worker_loop(self):
        """Periodically retrieves request from request queue, measure it, and
        put result in response queue"""
        logs.initialize(default_extras={
            'component': 'measurer',
            'subcomponent': 'worker',
        })
        logger.info('Starting one measure worker loop')
        while True:
            try:
                # 1. 获取任务 (包裹 try-except 以防队列本身报错)
                try:
                    request = self.get_task_from_request_queue()
                except Exception:
                    logger.error('Worker failed to get task: %s', traceback.format_exc())
                    time.sleep(MEASUREMENT_TIMEOUT)
                    continue

                logger.info(
                    'Measurer worker: Got request %s %s %d %d from request queue',
                    request.fuzzer, request.benchmark, request.trial_id,
                    request.cycle)
                
                # 2. 执行测量
                measured_snapshot = None
                try:
                    measured_snapshot = measure_manager.measure_snapshot_coverage(
                        request.fuzzer, request.benchmark, request.trial_id,
                        request.cycle, self.region_coverage)
                except Exception:
                    # [CRITICAL FIX] 捕获所有测量过程中的崩溃
                    logger.error('Worker CRASHED measuring cycle %d: %s', 
                                 request.cycle, traceback.format_exc())
                    # 此时 measured_snapshot 依然是 None，后面会触发 RetryRequest
                
                # 3. 发送结果 (无论是 Snapshot 还是 Retry)
                self.put_result_in_response_queue(measured_snapshot, request)

            except Exception:
                # [CRITICAL FIX] 这一层是最后的防线
                # 如果 put_result_in_response_queue 也挂了，必须捕获住，
                # 否则 Worker 进程会直接退出，导致 Manager 永久死锁。
                logger.error('Worker CRASHED in main loop (queue error?): %s', 
                             traceback.format_exc())
            
            time.sleep(MEASUREMENT_TIMEOUT)


class LocalMeasureWorker(BaseMeasureWorker):
    """Class that holds implementations of core methods for running a measure
    worker locally."""

    def get_task_from_request_queue(
            self) -> measurer_datatypes.SnapshotMeasureRequest:
        request = self.request_queue.get(block=True)
        return request

    def put_result_in_response_queue(
            self, measured_snapshot: Optional[Snapshot],
            request: measurer_datatypes.SnapshotMeasureRequest):
        if measured_snapshot:
            logger.info('Put measured snapshot in response_queue')
            self.response_queue.put(measured_snapshot)
            return

        # ---- failed path ----
        logger.warning(
            'Measurement failed or crashed. Sending RetryRequest for cycle %d',
            request.cycle
        )

        prev_fail = getattr(request, 'fail_count', 0) or 0
        next_fail = prev_fail + 1

        # 兼容两种 RetryRequest：
        # - 旧版：('fuzzer','benchmark','trial_id','cycle')
        # - 新版：('fuzzer','benchmark','trial_id','cycle','fail_count')
        fields = getattr(measurer_datatypes.RetryRequest, '_fields', ())
        has_fail_count_field = 'fail_count' in fields

        try:
            if has_fail_count_field:
                # 用“位置参数”构造更稳（namedtuple 的关键字参数在字段不匹配时会直接炸）
                retry_request = measurer_datatypes.RetryRequest(
                    request.fuzzer, request.benchmark, request.trial_id,
                    request.cycle, next_fail
                )
            else:
                retry_request = measurer_datatypes.RetryRequest(
                    request.fuzzer, request.benchmark, request.trial_id,
                    request.cycle
                )
        except TypeError:
            # 最后的兜底：即使上面判断失误，也保证不会把 worker 搞崩
            retry_request = measurer_datatypes.RetryRequest(
                request.fuzzer, request.benchmark, request.trial_id,
                request.cycle
            )

        self.response_queue.put(retry_request)