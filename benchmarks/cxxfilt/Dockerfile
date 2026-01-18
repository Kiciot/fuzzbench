# Copyright 2019 Google Inc.
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

# === 1. 网络代理配置 ===
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY
RUN git config --global http.proxy http://172.17.0.1:7890
RUN git config --global http.sslVerify false
# ======================

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    make \
    texinfo \
    flex \
    bison \
    zip

# === 2. 版本锁定: binutils-2_26 ===
# 锁定到 2.26 版本 (和 nm-new 保持一致)
RUN git clone \
    --depth 1 \
    --branch binutils-2_26 \
    git://sourceware.org/git/binutils-gdb.git binutils

WORKDIR binutils

# 复制构建脚本
COPY build.sh $SRC/
