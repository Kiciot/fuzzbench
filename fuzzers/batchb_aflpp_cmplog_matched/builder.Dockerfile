# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0.

ARG parent_image
FROM $parent_image

ARG UBUNTU_APT_MIRROR=
ARG UBUNTU_SECURITY_APT_MIRROR=
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG http_proxy=
ARG https_proxy=

ENV DEBIAN_FRONTEND=noninteractive

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
      > /etc/apt/apt.conf.d/80-retries; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      build-essential \
      python3-dev \
      python3-setuptools \
      automake \
      cmake \
      git \
      flex \
      bison \
      libglib2.0-dev \
      libpixman-1-dev \
      cargo \
      libgtk-3-dev \
      ninja-build \
      gcc-$(gcc --version | head -n1 | sed 's/\..*//' | sed 's/.* //')-plugin-dev \
      libstdc++-$(gcc --version | head -n1 | sed 's/\..*//' | sed 's/.* //')-dev; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    proxy="${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-}}}}"; \
    if [ -n "${proxy}" ]; then \
      git config --global http.proxy "${proxy}"; \
      git config --global https.proxy "${proxy}"; \
    fi; \
    git config --global http.version HTTP/1.1; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 120; \
    git config --global core.compression 0; \
    rm -rf /afl; \
    git init /afl; \
    git -C /afl remote add origin https://github.com/Kiciot/AFLplusplus; \
    ok=0; \
    for i in $(seq 1 8); do \
      if git -C /afl fetch --depth 1 origin b9b2d374f05d82319e5e8ef278aa0fa43b91dc51; then \
        ok=1; \
        break; \
      fi; \
      echo "AFL++ fetch failed (${i}/8), retrying" >&2; \
      sleep 10; \
    done; \
    [ "${ok}" = "1" ]; \
    git -C /afl checkout -f FETCH_HEAD; \
    test "$(git -C /afl rev-parse HEAD)" = "b9b2d374f05d82319e5e8ef278aa0fa43b91dc51"

RUN cd /afl && \
    unset CFLAGS CXXFLAGS && \
    export CC=clang AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make && \
    cp utils/aflpp_driver/libAFLDriver.a /
