# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

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


RUN set -eux; \
    apt-get update || (sleep 5 && apt-get update); \
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y || true; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
      curl \
      xz-utils \
      make \
      autoconf \
      automake \
      libtool \
      pkg-config \
    || (sleep 10 && apt-get update --fix-missing && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          ca-certificates git wget curl xz-utils make autoconf automake libtool pkg-config); \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0

WORKDIR $SRC


RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf freetype2; \
      if git clone --depth 1 https://github.com/freetype/freetype.git freetype2; then \
        break; \
      fi; \
      echo "git clone freetype failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -d freetype2

# 2) text-rendering-tests (TRT)
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf TRT; \
      if git clone --depth 1 https://github.com/unicode-org/text-rendering-tests.git TRT; then \
        break; \
      fi; \
      echo "git clone TRT failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -d TRT


RUN set -eux; \
    url="https://github.com/libarchive/libarchive/releases/download/v3.4.3/libarchive-3.4.3.tar.xz"; \
    for i in 1 2 3 4 5; do \
      rm -f libarchive-3.4.3.tar.xz; \
      if wget -O libarchive-3.4.3.tar.xz \
        --tries=5 --timeout=60 \
        -e use_proxy=yes \
        -e http_proxy="${HTTP_PROXY}" \
        -e https_proxy="${HTTPS_PROXY}" \
        "${url}"; then \
        break; \
      fi; \
      echo "wget libarchive failed, retry $i/5"; \
      sleep 5; \
    done; \
    test -s libarchive-3.4.3.tar.xz

COPY . $SRC/