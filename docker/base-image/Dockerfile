# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0

FROM ubuntu:focal

ENV DEBIAN_FRONTEND=noninteractive

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

# 通用下载代理开关（给 curl / pip 等）
ARG USE_PROXY=1
# apt 专用代理开关：1=走代理，0=禁用 apt 代理
ARG APT_USE_PROXY=1

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    USE_PROXY=${USE_PROXY} \
    APT_USE_PROXY=${APT_USE_PROXY}

# 默认改成 HTTPS 国内镜像，降低代理抖动影响
ARG UBUNTU_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu
ARG UBUNTU_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu

# Python 3.10.8 is not the default version in Ubuntu 20.04 (Focal Fossa).
ENV PYTHON_VERSION=3.10.8

# make 并行度可控：避免在小机器/CI 里把内存打爆
ARG MAKE_JOBS=0
ENV MAKE_JOBS=${MAKE_JOBS}

# -----------------------------
# APT robustness + mirror replace
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_MIRROR}|g" /etc/apt/sources.list || true; \
      sed -i "s|http://security.ubuntu.com/ubuntu|${UBUNTU_SECURITY_MIRROR}|g" /etc/apt/sources.list || true; \
      sed -i "s|https://archive.ubuntu.com/ubuntu|${UBUNTU_MIRROR}|g" /etc/apt/sources.list || true; \
      sed -i "s|https://security.ubuntu.com/ubuntu|${UBUNTU_SECURITY_MIRROR}|g" /etc/apt/sources.list || true; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      'Acquire::BrokenProxy "true";' \
      'Acquire::ForceIPv4 "true";' \
      > /etc/apt/apt.conf.d/80-retries; \
    if [ "${APT_USE_PROXY}" = "0" ]; then \
      printf '%s\n' \
        'Acquire::http::Proxy "false";' \
        'Acquire::https::Proxy "false";' \
        > /etc/apt/apt.conf.d/81-proxy-off; \
    fi

# -----------------------------
# Helper: robust apt install (no upgrade)
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
# Base deps (split into stages to reduce retry blast radius)
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
      liblzma-dev \
    ; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Helper: download-with-retry, proxy-first then direct fallback, multi-mirror
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
'  if [ "${USE_PROXY:-1}" = "1" ]; then' \
'    if curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 --connect-timeout 20 --max-time 600 -o "$out" "$url"; then' \
'      return 0' \
'    fi' \
'    echo "download failed via proxy: $url" >&2' \
'  fi' \
'  if env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 --connect-timeout 20 --max-time 600 -o "$out" "$url"; then' \
'    return 0' \
'  fi' \
'  echo "download failed via direct: $url" >&2' \
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
'echo "download permanently failed (all mirrors): $url1" >&2' \
'exit 1' \
      > /usr/local/bin/_curl_dl; \
    chmod +x /usr/local/bin/_curl_dl

# -----------------------------
# Build & install Python (download with mirrors)
# -----------------------------
RUN set -eux; \
    cd /tmp; \
    /usr/local/bin/_curl_dl \
      "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
      "https://registry.npmmirror.com/-/binary/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
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
# Install common python dependencies
# -----------------------------
COPY ./requirements.txt /tmp/requirements.txt
RUN set -eux; \
    pip install --retries 8 --timeout 120 -r /tmp/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple; \
    rm -f /tmp/requirements.txt

# -----------------------------
# Install google-cloud-cli (use keyring; avoid apt-key)
# -----------------------------
RUN set -eux; \
    /usr/local/bin/_curl_dl \
      "https://packages.cloud.google.com/apt/doc/apt-key.gpg" \
      "https://mirrors.cloud.google.com/apt/doc/apt-key.gpg" \
      "" \
      "/tmp/google-cloud.gpg"; \
    gpg --dearmor -o /usr/share/keyrings/google-cloud.gpg /tmp/google-cloud.gpg; \
    rm -f /tmp/google-cloud.gpg; \
    echo "deb [signed-by=/usr/share/keyrings/google-cloud.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list; \
    /usr/local/bin/_apt_install google-cloud-cli; \
    rm -rf /var/lib/apt/lists/*