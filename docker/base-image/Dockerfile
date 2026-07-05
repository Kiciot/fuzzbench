# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0

FROM ubuntu:focal

ENV DEBIAN_FRONTEND=noninteractive

# -----------------------------
# Proxy policy
# -----------------------------
# Keep proxy values empty by default; pass build args explicitly if needed.
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=localhost,127.0.0.1,::1

ARG USE_PROXY=0
ARG APT_USE_PROXY=0

ENV USE_PROXY=${USE_PROXY} \
    APT_USE_PROXY=${APT_USE_PROXY} \
    NO_PROXY=${NO_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# Ubuntu mirror
# -----------------------------
# 用 HTTP 源做 bootstrap，避免 ca-certificates 尚未安装时 HTTPS apt 源校验失败。
ARG UBUNTU_APT_MIRROR=
ARG UBUNTU_SECURITY_APT_MIRROR=

# Python 3.10.8 is not the default version in Ubuntu 20.04.
ENV PYTHON_VERSION=3.10.8

# make 并行度可控，避免构建 Python 时内存打爆。
ARG MAKE_JOBS=0
ENV MAKE_JOBS=${MAKE_JOBS}

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
ARG PIP_USE_LEGACY_RESOLVER=0

# -----------------------------
# APT robustness + mirror replace
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      if [ -n "${UBUNTU_APT_MIRROR}" ]; then \
        security_mirror="${UBUNTU_SECURITY_APT_MIRROR:-${UBUNTU_APT_MIRROR}}"; \
        sed -i "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_APT_MIRROR}|g" /etc/apt/sources.list || true; \
        sed -i "s|http://security.ubuntu.com/ubuntu|${security_mirror}|g" /etc/apt/sources.list || true; \
        sed -i "s|https://archive.ubuntu.com/ubuntu|${UBUNTU_APT_MIRROR}|g" /etc/apt/sources.list || true; \
        sed -i "s|https://security.ubuntu.com/ubuntu|${security_mirror}|g" /etc/apt/sources.list || true; \
      fi; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      'Acquire::BrokenProxy "true";' \
      'Acquire::ForceIPv4 "true";' \
      > /etc/apt/apt.conf.d/80-retries

# -----------------------------
# Helper: robust apt install
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
'#!/bin/sh' \
'set -eu' \
'i=1' \
'while [ "$i" -le 8 ]; do' \
'  rm -rf /var/lib/apt/lists/partial || true' \
'  mkdir -p /var/lib/apt/lists/partial' \
'  if apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --fix-missing "$@"; then' \
'    exit 0' \
'  fi' \
'  echo "apt-get install failed ($i/8): $*" >&2' \
'  apt-get clean || true' \
'  rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/partial/* /var/cache/apt/pkgcache.bin /var/cache/apt/srcpkgcache.bin || true' \
'  i=$((i+1))' \
'  sleep 5' \
'done' \
'echo "apt-get install permanently failed: $*" >&2' \
'exit 1' \
      > /usr/local/bin/_apt_install; \
    chmod +x /usr/local/bin/_apt_install

# -----------------------------
# Base deps
# -----------------------------
RUN set -eux; \
    /usr/local/bin/_apt_install \
      ca-certificates \
      curl \
      xz-utils \
      apt-transport-https \
      gnupg \
      rsync

RUN set -eux; \
    /usr/local/bin/_apt_install \
      build-essential

RUN set -eux; \
    /usr/local/bin/_apt_install \
      zlib1g-dev \
      libssl-dev \
      libffi-dev \
      libsqlite3-dev \
      libbz2-dev \
      liblzma-dev; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Helper: download with retry
# usage: _curl_dl <url1> [url2] [url3] <out>
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
'#!/bin/sh' \
'set -eu' \
'url1="${1:-}"' \
'url2="${2:-}"' \
'url3="${3:-}"' \
'out="${4:-}"' \
'[ -n "$url1" ] && [ -n "$out" ] || { echo "usage: _curl_dl <url1> [url2] [url3] <out>" >&2; exit 2; }' \
'' \
'try_one() {' \
'  url="$1"' \
'  if curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 --connect-timeout 20 --max-time 600 -o "$out" "$url"; then' \
'    return 0' \
'  fi' \
'  echo "download failed: $url" >&2' \
'  return 1' \
'}' \
'' \
'for url in "$url1" "$url2" "$url3"; do' \
'  [ -n "$url" ] || continue' \
'  i=1' \
'  while [ "$i" -le 3 ]; do' \
'    rm -f "$out"' \
'    if try_one "$url"; then' \
'      exit 0' \
'    fi' \
'    i=$((i+1))' \
'    sleep 3' \
'  done' \
'done' \
'' \
'echo "download permanently failed: $url1" >&2' \
'exit 1' \
      > /usr/local/bin/_curl_dl; \
    chmod +x /usr/local/bin/_curl_dl

# -----------------------------
# Build & install Python
# -----------------------------
RUN set -eux; \
    cd /tmp; \
    /usr/local/bin/_curl_dl \
      "https://registry.npmmirror.com/-/binary/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
      "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
      "" \
      "/tmp/Python-${PYTHON_VERSION}.tar.xz"; \
    tar -xf "/tmp/Python-${PYTHON_VERSION}.tar.xz" > /dev/null; \
    cd "Python-${PYTHON_VERSION}"; \
    ./configure \
      --enable-loadable-sqlite-extensions \
      --enable-optimizations \
      > /dev/null; \
    jobs="${MAKE_JOBS}"; \
    if [ "$jobs" = "0" ]; then jobs="$(nproc)"; fi; \
    make -j"$jobs" install > /dev/null; \
    cd /; \
    rm -rf "/tmp/Python-${PYTHON_VERSION}.tar.xz" "/tmp/Python-${PYTHON_VERSION}"; \
    ln -sf /usr/local/bin/python3 /usr/local/bin/python; \
    ln -sf /usr/local/bin/pip3 /usr/local/bin/pip

# -----------------------------
# Install Python dependencies
# -----------------------------
COPY ./requirements.txt /tmp/requirements.txt
RUN set -eux; \
    pip_index_args="-i ${PIP_INDEX_URL}"; \
    if [ -n "${PIP_TRUSTED_HOST}" ]; then \
      pip_index_args="${pip_index_args} --trusted-host ${PIP_TRUSTED_HOST}"; \
    fi; \
    resolver_args=""; \
    if [ "${PIP_USE_LEGACY_RESOLVER}" = "1" ]; then \
      resolver_args="--use-deprecated=legacy-resolver"; \
    fi; \
    python3 -m pip install \
        --retries 8 \
        --timeout 120 \
        --no-cache-dir \
        --upgrade pip setuptools \
        ${pip_index_args}; \
    python3 -m pip install \
        --retries 8 \
        --timeout 120 \
        --no-cache-dir \
        -r /tmp/requirements.txt \
        ${resolver_args} \
        ${pip_index_args}; \
    rm -f /tmp/requirements.txt

# -----------------------------
# Local FuzzBench build
# -----------------------------
# 本地实验不需要 google-cloud-cli。
# 之前失败正是卡在 packages.cloud.google.com / google-cloud-cli 这一层。
RUN set -eux; \
    echo "Skipping google-cloud-cli installation for local FuzzBench build"