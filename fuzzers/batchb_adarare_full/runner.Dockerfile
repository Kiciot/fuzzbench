# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

ARG image_namespace=gcr.io/fuzzbench-batchb-focused
FROM ${image_namespace}/base-image

# This makes interactive docker runs painless:
ENV LD_LIBRARY_PATH="$LD_LIBRARY_PATH:/out"
#ENV AFL_MAP_SIZE=2621440
ENV PATH="$PATH:/out"
ENV AFL_SKIP_CPUFREQ=1
ENV AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1
ENV AFL_TESTCACHE_SIZE=2
# RUN apt-get update && apt-get upgrade && apt install -y unzip git gdb joe
# Enable AdaRare/Bandit scheduler inside afl-fuzz.
ENV AFL_BANDIT=1
ENV AFL_BANDIT_WINDOW_MS=5000
ENV AFL_ADARARE_MODE=active
ENV AFL_ADARARE_POLICY=linucb
ENV AFL_ADARARE_ENABLE_A6=1
ENV AFL_ADARARE_RARITY_CONTEXT=1
ENV AFL_ADARARE_RARITY_REWARD=1
ENV AFL_ADARARE_RARITY_GATE=1
ENV AFL_ADARARE_TELEMETRY=1
ENV AFL_ADARARE_AUDIT=1
