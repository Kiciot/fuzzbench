# Copyright 2019 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ==============================
# 1) Proxy (build-time configurable)
# ==============================
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ==============================
# 2) APT stability: mirror + retries + timeouts
# ==============================
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
    fi; \
    printf 'Acquire::Retries "8";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\nAcquire::http::Pipeline-Depth "0";\n' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# ==============================
# 3) Git robustness (proxy + low-speed + optional SSL off)
# ==============================
ARG GIT_SSL_NO_VERIFY=0
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    if [ "${GIT_SSL_NO_VERIFY}" = "1" ]; then \
      git config --global http.sslVerify false; \
    fi

# ==============================
# 4) Build deps (with retries)
# ==============================
# Binutils build deps: texinfo flex bison; plus zip for seed corpus packaging.
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        make \
        texinfo \
        flex \
        bison \
        zip \
        git \
      && break; \
      echo "apt-get failed, retry $i/5"; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# ==============================
# 5) Pin binutils to tag: binutils-2_26
# ==============================
WORKDIR $SRC
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf binutils; \
      git clone --depth 1 --branch binutils-2_26 https://github.com/bminor/binutils-gdb binutils && break; \
      echo "git clone binutils failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d binutils

WORKDIR $SRC/binutils

# Copy build script last for better Docker layer caching
COPY build.sh $SRC/