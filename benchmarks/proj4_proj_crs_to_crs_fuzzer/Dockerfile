# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=localhost,127.0.0.1,::1
ARG UBUNTU_APT_MIRROR=
ARG UBUNTU_SECURITY_APT_MIRROR=
ARG GIT_CLONE_RETRIES=6
ARG PROJ_COMMIT=a7482d3775f2e346f3680363dd2d641add3e68b2

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- APT: optional mirror + retries/timeouts ----
RUN set -eux; \
    if [ -n "${UBUNTU_APT_MIRROR}" ]; then \
      security_mirror="${UBUNTU_SECURITY_APT_MIRROR:-${UBUNTU_APT_MIRROR}}"; \
      sed -i "s|http://archive.ubuntu.com/ubuntu/|${UBUNTU_APT_MIRROR}/|g" /etc/apt/sources.list || true; \
      sed -i "s|http://security.ubuntu.com/ubuntu/|${security_mirror}/|g" /etc/apt/sources.list || true; \
    fi; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-retries; \
    apt-get update; \
    apt-get install -y --no-install-recommends --fix-missing \
        make autoconf automake libtool g++ \
        sqlite3 libsqlite3-dev \
        pkg-config wget ca-certificates \
        liblzma-dev; \
    rm -rf /var/lib/apt/lists/*

# ---- GIT: proxy + robustness knobs ----
RUN set -eux; \
    if [ -n "${HTTP_PROXY}" ]; then git config --global http.proxy "${HTTP_PROXY}"; fi; \
    if [ -n "${HTTPS_PROXY}" ]; then git config --global https.proxy "${HTTPS_PROXY}"; fi; \
    git config --global http.version HTTP/1.1; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 120; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0

# PROJ: pinned commit matching benchmark.yaml
RUN set -eux; \
    rm -rf PROJ; \
    git init PROJ; \
    git -C PROJ remote add origin https://github.com/OSGeo/PROJ; \
    ok=0; \
    for i in $(seq 1 "${GIT_CLONE_RETRIES}"); do \
      if git -C PROJ fetch --depth 1 origin "${PROJ_COMMIT}"; then \
        ok=1; \
        break; \
      fi; \
      echo "PROJ fetch failed (${i}/${GIT_CLONE_RETRIES}), retrying" >&2; \
      sleep 10; \
    done; \
    [ "${ok}" = "1" ]; \
    git -C PROJ checkout -f FETCH_HEAD; \
    rm -f PROJ/.git/shallow; \
    test "$(git -C PROJ rev-parse HEAD)" = "${PROJ_COMMIT}"

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
    git -C PROJ/libtiff checkout FETCH_HEAD; \
    # 【终极防封杀魔法】从“getting config.guess”这一行开始，把文件末尾所有的瞎下载代码全删掉！
    sed -i '/getting config\.guess/,$d' PROJ/libtiff/autogen.sh

WORKDIR PROJ

COPY third_party/build.sh $SRC/

# Fix Fuzz Introspector build by using LLVM old pass manager
# https://github.com/ossf/fuzz-introspector/issues/305
ENV OLD_LLVMPASS=1