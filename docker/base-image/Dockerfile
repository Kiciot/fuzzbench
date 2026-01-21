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
# 代理总开关：代理不稳定时可直接 --build-arg USE_PROXY=0
ARG USE_PROXY=1

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# Optional: allow overriding Ubuntu mirror if your route makes some mirrors flaky.
ARG UBUNTU_MIRROR=http://archive.ubuntu.com/ubuntu
ARG UBUNTU_SECURITY_MIRROR=http://security.ubuntu.com/ubuntu

# Python 3.10.8 is not the default version in Ubuntu 20.04 (Focal Fossa).
ENV PYTHON_VERSION=3.10.8

# make 并行度可控：避免在小机器/CI 里把内存打爆
ARG MAKE_JOBS=0

# -----------------------------
# APT robustness (retries/timeouts) + optional mirror replace
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_MIRROR}|g" /etc/apt/sources.list || true; \
      sed -i "s|http://security.ubuntu.com/ubuntu|${UBUNTU_SECURITY_MIRROR}|g" /etc/apt/sources.list || true; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-retries

# -----------------------------
# Helper: robust apt install (no upgrade)
# -----------------------------
RUN set -eux; \
    cat > /usr/local/bin/_apt_install <<'SH'; \
#!/bin/sh
set -eu
i=1
while [ "$i" -le 8 ]; do
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" && \
  exit 0
  echo "apt-get install failed ($i/8): $*" >&2
  i=$((i+1))
  sleep 5
  apt-get update --fix-missing || true
done
echo "apt-get install permanently failed: $*" >&2
exit 1
SH
    chmod +x /usr/local/bin/_apt_install

# -----------------------------
# Base deps (curl first; ca-certificates first)
# -----------------------------
RUN set -eux; \
    /usr/local/bin/_apt_install \
      ca-certificates \
      curl \
      xz-utils \
      build-essential \
      zlib1g-dev \
      libssl-dev \
      libffi-dev \
      libsqlite3-dev \
      libbz2-dev \
      liblzma-dev \
      gnupg \
      rsync \
      apt-transport-https \
    ; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Helper: download-with-retry, proxy-first then direct fallback, multi-mirror
# usage: _curl_dl <url1> [url2] [url3] <out>
# -----------------------------
RUN set -eux; \
    cat > /usr/local/bin/_curl_dl <<'SH'; \
#!/bin/sh
set -eu
url1="${1:-}"
url2="${2:-}"
url3="${3:-}"
out="${4:-}"
[ -n "$url1" ] && [ -n "$out" ] || { echo "usage: _curl_dl <url1> [url2] [url3] <out>" >&2; exit 2; }

try_one() {
  url="$1"
  # 代理优先（如果 USE_PROXY=1），失败后再直连兜底
  if [ "${USE_PROXY:-1}" = "1" ]; then
    # 使用环境变量代理
    if curl -fL \
        --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 \
        --connect-timeout 20 --max-time 600 \
        -o "$out" "$url"; then
      return 0
    fi
    echo "download failed via proxy: $url" >&2
  fi

  # 直连兜底：清掉代理环境变量
  if env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
       curl -fL \
        --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 \
        --connect-timeout 20 --max-time 600 \
        -o "$out" "$url"; then
    return 0
  fi
  echo "download failed via direct: $url" >&2
  return 1
}

for url in "$url1" "$url2" "$url3"; do
  [ -n "$url" ] || continue
  i=1
  while [ "$i" -le 3 ]; do
    rm -f "$out"
    if try_one "$url"; then
      exit 0
    fi
    i=$((i+1))
    sleep 3
  done
done

echo "download permanently failed (all mirrors): $url1" >&2
exit 1
SH
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
    pip install -r /tmp/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple; \
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