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

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT stability: domestic mirror + no apt proxy
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|https://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|https://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
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
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# Tooling install
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      if env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
        apt-get update && \
        env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          ca-certificates \
          curl \
          git \
          ragel \
          pkg-config; then \
        break; \
      fi; \
      echo "apt-get failed, retry $i/5"; \
      apt-get clean || true; \
      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/partial/* || true; \
      sleep 10; \
    done; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Git / curl robustness
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
# Helper: download with retry
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      'set -euo pipefail' \
      'out="$1"' \
      'shift' \
      'n="${DL_RETRY_N:-8}"' \
      'sleep_s="${DL_RETRY_SLEEP:-10}"' \
      'for url in "$@"; do' \
      '  [ -n "$url" ] || continue' \
      '  i=1' \
      '  while [ "$i" -le "$n" ]; do' \
      '    rm -f "$out"' \
      '    if curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 600 --connect-timeout 30 --max-time 900 -o "$out" "$url"; then' \
      '      exit 0' \
      '    fi' \
      '    echo "[download_retry] failed attempt ${i}/${n}: $url" >&2' \
      '    i=$((i+1))' \
      '    sleep "$sleep_s"' \
      '  done' \
      'done' \
      'echo "[download_retry] permanently failed: $*" >&2' \
      'exit 1' \
      > /usr/local/bin/download_retry; \
    chmod +x /usr/local/bin/download_retry

# -----------------------------
# Fetch harfbuzz.
#
# Use tarball instead of git clone because git clone repeatedly failed with
# GnuTLS recv error / early EOF / index-pack failed in the current network.
# -----------------------------
WORKDIR $SRC

RUN set -eux; \
    rm -rf harfbuzz harfbuzz.tar.gz; \
    download_retry harfbuzz.tar.gz \
      "https://github.com/harfbuzz/harfbuzz/archive/refs/heads/main.tar.gz" \
      "https://codeload.github.com/harfbuzz/harfbuzz/tar.gz/refs/heads/main"; \
    test -s harfbuzz.tar.gz; \
    mkdir -p harfbuzz; \
    tar -xzf harfbuzz.tar.gz -C harfbuzz --strip-components=1; \
    rm -f harfbuzz.tar.gz; \
    test -d harfbuzz

WORKDIR $SRC/harfbuzz

COPY build.sh $SRC/