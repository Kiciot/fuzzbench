# Copyright 2018 Google Inc.
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

# -----------------------------
# APT: 无代理 + 国内源 + 稳定安装
# -----------------------------
RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY="" apt-get update; \
    http_proxy="" https_proxy="" HTTP_PROXY="" HTTPS_PROXY="" apt-get install -y --no-install-recommends --fix-missing \
        make cmake python-all-dev python3-all-dev python3-pip; \
    ln -s /usr/local/bin/pip3 /usr/local/bin/pip || true; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# 为后续拉取代码和编译注入全局代理
# -----------------------------
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# -----------------------------
# Git 防封杀与大文件配置
# -----------------------------
RUN set -eux; \
    git config --global http.proxy "http://172.17.0.1:7890"; \
    git config --global https.proxy "http://172.17.0.1:7890"; \
    git config --global http.sslVerify false; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0

# -----------------------------
# 源码拉取与构建准备
# -----------------------------
RUN git clone --recursive -b development https://github.com/Mbed-TLS/mbedtls.git mbedtls
RUN git clone --depth 1 https://github.com/google/boringssl.git boringssl
RUN git clone --recursive https://github.com/openssl/openssl.git openssl

WORKDIR mbedtls
COPY build.sh $SRC/