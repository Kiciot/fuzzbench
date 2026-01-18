# Copyright 2016 Google Inc.
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
#
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
RUN git config --global http.proxy http://172.17.0.1:7890
RUN git config --global http.sslVerify false

RUN apt-get update && apt-get install -y make wget

# === 2. 版本锁定: 2014-12-09 ===
# 这是一个 GTS 标准快照版本
RUN git clone \
    --depth 1 \
    --branch 2014-12-09 \
    https://github.com/google/re2.git

WORKDIR re2

RUN wget --no-check-certificate \
    -e use_proxy=yes -e http_proxy=http://172.17.0.1:7890 \
    -qO $OUT/fuzzer.dict \
    https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/regexp.dict

# 复制构建脚本和 fuzz target
COPY build.sh target.cc $SRC/