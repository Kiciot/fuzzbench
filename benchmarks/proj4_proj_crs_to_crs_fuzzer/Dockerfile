# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

# Give git/curl the proxy; force apt to ignore proxy via env -u (below).
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- APT: no proxy + retries/timeouts (more robust under flaky HTTP proxies) ----
RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list || true; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-retries; \
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY apt-get update; \
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
      apt-get install -y --no-install-recommends --fix-missing \
        make autoconf automake libtool g++ \
        sqlite3 libsqlite3-dev \
        pkg-config wget ca-certificates \
        liblzma-dev; \
    rm -rf /var/lib/apt/lists/*

# ---- GIT: proxy + robustness knobs ----
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.version HTTP/1.1; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0

# PROJ: shallow clone (default branch)
RUN set -eux; \
    git clone --depth 1 https://github.com/OSGeo/PROJ PROJ

# curl: pinned commit via shallow fetch
RUN set -eux; \
    git init PROJ/curl; \
    git -C PROJ/curl remote add origin https://github.com/curl/curl.git; \
    for i in 1 2 3 4 5; do \
      git -C PROJ/curl fetch --depth 1 origin c12fb3ddaf48e709a7a4deaa55ec485e4df163ee && break || (sleep 5); \
    done; \
    git -C PROJ/curl checkout FETCH_HEAD

# libtiff: pinned commit via shallow fetch (gitlab)
RUN set -eux; \
    git init PROJ/libtiff; \
    git -C PROJ/libtiff remote add origin https://gitlab.com/libtiff/libtiff.git; \
    for i in 1 2 3 4 5; do \
      git -C PROJ/libtiff fetch --depth 1 origin c8e1289deff3fa60ba833ccec6c030934b02c281 && break || (sleep 5); \
    done; \
    git -C PROJ/libtiff checkout FETCH_HEAD

WORKDIR PROJ

COPY third_party/build.sh $SRC/

# Fix Fuzz Introspector build by using LLVM old pass manager
# https://github.com/ossf/fuzz-introspector/issues/305
ENV OLD_LLVMPASS=1