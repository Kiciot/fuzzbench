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
# APT: domestic mirror + no apt proxy
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
      sed -i 's|https://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
      sed -i 's|https://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      'Acquire::ForceIPv4 "true";' \
      'Acquire::http::Proxy "false";' \
      'Acquire::https::Proxy "false";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries; \
    for i in 1 2 3 4 5; do \
      if env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
        apt-get update && \
        env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --fix-missing \
          make \
          cmake \
          git \
          ca-certificates \
          python-all-dev \
          python3-all-dev \
          python3-pip; then \
        break; \
      fi; \
      echo "apt-get failed, retry $i/5"; \
      apt-get clean || true; \
      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/partial/* || true; \
      sleep 10; \
    done; \
    ln -sf "$(command -v pip3)" /usr/local/bin/pip || true; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Proxy for git / curl / build scripts
# -----------------------------
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# -----------------------------
# Git robustness
# -----------------------------
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.version HTTP/1.1; \
    git config --global http.sslVerify false; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    git config --global pack.threads 1; \
    git config --global http.maxRequests 4

# -----------------------------
# Generic git retry helper
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      'set -euo pipefail' \
      'n="${GIT_RETRY_N:-8}"' \
      'sleep_s="${GIT_RETRY_SLEEP:-10}"' \
      'i=1' \
      'while true; do' \
      '  if "$@"; then' \
      '    exit 0' \
      '  fi' \
      '  if [ "$i" -ge "$n" ]; then' \
      '    echo "[git_retry] failed after ${n} attempts: $*" >&2' \
      '    exit 1' \
      '  fi' \
      '  echo "[git_retry] attempt ${i}/${n} failed; retrying in ${sleep_s}s: $*" >&2' \
      '  sleep "${sleep_s}"' \
      '  i=$((i+1))' \
      'done' \
      > /usr/local/bin/git_retry; \
    chmod +x /usr/local/bin/git_retry

# -----------------------------
# Source checkout.
#
# mbedtls requires recursive checkout, but use shallow clone and shallow
# submodules to reduce network pressure.
# -----------------------------
WORKDIR $SRC

RUN set -eux; \
    git_retry git clone \
      --depth 1 \
      --single-branch \
      --branch development \
      --recurse-submodules \
      --shallow-submodules \
      https://github.com/Mbed-TLS/mbedtls.git \
      mbedtls

RUN set -eux; \
    git_retry git clone \
      --depth 1 \
      --single-branch \
      https://github.com/google/boringssl.git \
      boringssl

RUN set -eux; \
    git_retry git clone \
      --depth 1 \
      --single-branch \
      https://github.com/openssl/openssl.git \
      openssl

WORKDIR $SRC/mbedtls

COPY build.sh $SRC/