# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# ...
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# --- Proxy (keep both upper/lower to cover all tools) ---
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# --- Git robustness knobs (apply globally so build scripts inherit) ---
RUN set -eux; \
  git config --global http.proxy "${HTTP_PROXY}"; \
  git config --global https.proxy "${HTTPS_PROXY}"; \
  git config --global http.version HTTP/1.1; \
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 600; \
  git config --global http.postBuffer 524288000; \
  git config --global core.compression 0; \
  git config --global transfer.fsckobjects false; \
  git config --global fetch.fsckobjects false; \
  git config --global receive.fsckobjects false; \
  git config --global pack.threads 1; \
  git config --global http.maxRequests 4

# A small helper for retrying git operations in Docker build.
# Fixed parser issue by using printf instead of EOF heredoc.
RUN set -eux; \
  printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -euo pipefail' \
    'n="${GIT_RETRY_N:-6}"' \
    'sleep_s="${GIT_RETRY_SLEEP:-8}"' \
    'i=1' \
    'while true; do' \
    '  if "$@"; then' \
    '    exit 0' \
    '  fi' \
    '  if [ "$i" -ge "$n" ]; then' \
    '    echo "[git_retry] failed after ${n} attempts: $*" >&2' \
    '    exit 1' \
    '  fi' \
    '  echo "[git_retry] attempt ${i} failed; retrying in ${sleep_s}s: $*" >&2' \
    '  sleep "${sleep_s}"' \
    '  i=$((i+1))' \
    'done' \
    > /usr/local/bin/git_retry; \
  chmod +x /usr/local/bin/git_retry

# Curl will be checked out to the commit hash specified in benchmark.yaml.
# Use retry for the initial clones too (these are also subject to transient network).
RUN set -eux; \
  git_retry git clone https://github.com/curl/curl-fuzzer /src/curl_fuzzer; \
  git -C /src/curl_fuzzer checkout dd486c1e5910e722e43c451d4de928ac80f5967d; \
  git_retry git clone --depth 1 --single-branch https://github.com/curl/curl.git /src/curl

# --- Proactive Network Armor (防黑盒脚本背刺) ---
RUN set -eux; \
  sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
  sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Proxy "false";' \
    'Acquire::https::Proxy "false";' \
    > /etc/apt/apt.conf.d/80-retries; \
  mv /usr/bin/wget /usr/bin/wget_orig || true; \
  printf '%s\n' \
    '#!/bin/sh' \
    'exec /usr/bin/wget_orig --no-check-certificate --tries=10 "$@"' \
    > /usr/bin/wget; \
  chmod +x /usr/bin/wget

# Use curl-fuzzer's scripts to get latest dependencies.
# This step later triggers OpenSSL clone in build.sh scripts; it will inherit git configs above.
RUN set -eux; \
    # 增加调试输出
    /bin/bash -x "$SRC/curl_fuzzer/scripts/ossfuzzdeps.sh"

WORKDIR $SRC/curl_fuzzer

# Keep build.sh as-is (but it will benefit from global git settings).
COPY build.sh $SRC/