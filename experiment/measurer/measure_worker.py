# Copyright 2024 Google LLC
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
    """Base class for measure worker. Encapsulates core methods that will be
    implemented for Local and Google Cloud measure workers."""

    def __init__(self, config: Dict):
        self.request_queue = config['request_queue']
        self.response_queue = config['response_queue']
        self.region_coverage = config['region_coverage']

    def get_task_from_request_queue(self):
        """"Get task from request queue"""
        raise NotImplementedError

    def put_result_in_response_queue(self, measured_snapshot, request):
        """Save measurement result in response queue, for the measure manager to
        retrieve"""
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
            # 'SnapshotMeasureRequest', ['fuzzer', 'benchmark', 'trial_id',
            # 'cycle']
            try:
                request = self.get_task_from_request_queue()
            except Exception: # pylint: disable=broad-except
                # 如果连取任务都失败了，记录日志并重试
                logger.error('Worker failed to get task: %s', traceback.format_exc())
                time.sleep(MEASUREMENT_TIMEOUT)
                continue

            logger.info(
                'Measurer worker: Got request %s %s %d %d from request queue',
                request.fuzzer, request.benchmark, request.trial_id,
                request.cycle)
            
            # [CRITICAL FIX] 加上全包裹的 try-except
            try:
                measured_snapshot = measure_manager.measure_snapshot_coverage(
                    request.fuzzer, request.benchmark, request.trial_id,
                    request.cycle, self.region_coverage)
                
                # 正常情况：提交结果
                self.put_result_in_response_queue(measured_snapshot, request)

            except Exception:  # pylint: disable=broad-except
                # 异常情况：记录堆栈，并发送 RetryRequest 解除 Manager 死锁
                error_msg = traceback.format_exc()
                logger.error('Worker crashed during measurement: %s', error_msg)
                
                # 构造一个 RetryRequest 通知 Manager 这个任务失败了
                # 这样 Manager 就会把它从 pending 列表中移除，避免死锁
                retry_request = measurer_datatypes.RetryRequest(
                    request.fuzzer, request.benchmark, request.trial_id,
                    request.cycle, fail_count=1
                )
                
                # 尝试把失败消息发回去，如果发不回去也没办法了
                try:
                    self.response_queue.put(retry_request)
                except Exception:
                    logger.error('Worker failed to send retry request.')

            time.sleep(MEASUREMENT_TIMEOUT)


class LocalMeasureWorker(BaseMeasureWorker):
    """Class that holds implementations of core methods for running a measure
    worker locally."""

    def get_task_from_request_queue(
            self) -> measurer_datatypes.SnapshotMeasureRequest:
        """Get item from request multiprocessing queue, block if necessary until
        an item is available"""
        request = self.request_queue.get(block=True)
        return request

    def put_result_in_response_queue(
            self, measured_snapshot: Optional[Snapshot],
            request: measurer_datatypes.SnapshotMeasureRequest):
        if measured_snapshot:
            logger.info('Put measured snapshot in response_queue')
            self.response_queue.put(measured_snapshot)
        else:
            retry_request = measurer_datatypes.RetryRequest(
                request.fuzzer, request.benchmark, request.trial_id,
                request.cycle)
            self.response_queue.put(retry_request)