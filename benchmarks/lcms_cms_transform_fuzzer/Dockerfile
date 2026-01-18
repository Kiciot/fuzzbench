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
#
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY
RUN apt-get update && \
    apt-get install -y \
    make \
    automake \
    libtool \
    wget
RUN git clone https://github.com/mm2/Little-CMS.git lcms && \
    cd lcms && \
    git checkout f9d75c31e670d97960f89839352e008709337581

WORKDIR lcms

# === 3. 下载字典 ===
# 加上代理参数，防止下载失败
RUN wget --no-check-certificate \
    -e use_proxy=yes -e http_proxy=http://172.17.0.1:7890 \
    -qO $OUT/cms_transform_fuzzer.dict \
    https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/icc.dict

# 复制构建脚本、Fuzz Target 和 种子
COPY cms_transform_fuzzer.cc build.sh $SRC/
ADD seeds /opt/seeds