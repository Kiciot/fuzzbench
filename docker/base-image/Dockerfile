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

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# Optional: allow overriding Ubuntu mirror if your proxy/route makes some mirrors flaky.
# Example: --build-arg UBUNTU_MIRROR=http://archive.ubuntu.com/ubuntu
ARG UBUNTU_MIRROR=http://archive.ubuntu.com/ubuntu
ARG UBUNTU_SECURITY_MIRROR=http://security.ubuntu.com/ubuntu

# Python 3.10.8 is not the default version in Ubuntu 20.04 (Focal Fossa).
ENV PYTHON_VERSION=3.10.8

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
# Install build deps (with retry loop)
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5 6 7 8; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get upgrade -y && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
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
      && break; \
      echo "apt-get failed ($i/8), retrying..."; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Build & install Python (download with retries)
# -----------------------------
RUN set -eux; \
    cd /tmp; \
    curl -fsSL \
      --retry 8 \
      --retry-connrefused \
      --retry-delay 5 \
      --retry-max-time 300 \
      --connect-timeout 20 \
      --max-time 600 \
      -o "Python-${PYTHON_VERSION}.tar.xz" \
      "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz"; \
    tar -xf "Python-${PYTHON_VERSION}.tar.xz" > /dev/null; \
    cd "Python-${PYTHON_VERSION}"; \
    ./configure \
      --enable-loadable-sqlite-extensions \
      --enable-optimizations \
      > /dev/null; \
    make -j"$(nproc)" install > /dev/null; \
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
# Install deps required by google-cloud-cli (with retry loop)
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5 6 7 8; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        apt-transport-https \
        ca-certificates \
        rsync \
        gnupg \
      && break; \
      echo "apt-get (cloud deps) failed ($i/8), retrying..."; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Install google-cloud-cli (use keyring; avoid apt-key)
# -----------------------------
RUN set -eux; \
    curl -fsSL \
      --retry 8 \
      --retry-connrefused \
      --retry-delay 5 \
      --retry-max-time 300 \
      --connect-timeout 20 \
      --max-time 600 \
      "https://packages.cloud.google.com/apt/doc/apt-key.gpg" \
      | gpg --dearmor -o /usr/share/keyrings/google-cloud.gpg; \
    echo "deb [signed-by=/usr/share/keyrings/google-cloud.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list; \
    for i in 1 2 3 4 5 6 7 8; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends google-cloud-cli \
      && break; \
      echo "apt-get (google-cloud-cli) failed ($i/8), retrying..."; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*