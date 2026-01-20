# Copyright 2016 Google Inc.
# Licensed under the Apache License, Version 2.0
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
    ftp_proxy=${HTTP_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT stability: mirror + retries + timeouts
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      'DPkg::Lock::Timeout "120";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# Tooling install (minimal but robust)
# -----------------------------
RUN set -eux; \
    apt-get update || (sleep 5 && apt-get update); \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      make \
    || (sleep 10 && apt-get update --fix-missing && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          ca-certificates git make); \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Git robustness (proxy + low-speed + large transfers)
# -----------------------------
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0

# -----------------------------
# Fetch OpenSSL (retry clone)
# -----------------------------
WORKDIR $SRC
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf openssl; \
      if git clone --depth 1 --branch openssl-3.0.7 https://github.com/openssl/openssl.git openssl; then \
        break; \
      fi; \
      echo "git clone openssl failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -d openssl

WORKDIR $SRC/openssl

# Copy build script last for better layer caching
COPY build.sh $SRC/