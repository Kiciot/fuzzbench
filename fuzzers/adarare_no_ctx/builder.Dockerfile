# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0

ARG parent_image
FROM $parent_image

# -----------------------------------------------------------------------------
# Proxy (keep for git/cargo; apt will explicitly bypass)
# -----------------------------------------------------------------------------
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# -----------------------------------------------------------------------------
# APT: TUNA mirror + bypass proxy for apt-get (stable + fast in CN)
# -----------------------------------------------------------------------------
RUN set -eux; \
    sed -i 's/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    sed -i 's/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    sed -i 's/mirrors.edge.kernel.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list; \
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY apt-get update; \
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        clang \
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
        ninja-build \
        libgtk-3-dev \
        gcc-plugin-dev \
        libstdc++-dev \
        ca-certificates \
    ; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Git hardening: proxy + tolerate slow links + retries
# -----------------------------------------------------------------------------
RUN set -eux; \
    git config --global http.proxy "$HTTP_PROXY"; \
    git config --global https.proxy "$HTTPS_PROXY"; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global http.version HTTP/1.1

# -----------------------------------------------------------------------------
# AFL++ source fetch (robust): shallow/partial clone + retry + pinned commit
# -----------------------------------------------------------------------------
ARG AFLPP_REPO=https://github.com/Kiciot/AFLplusplus
ARG AFLPP_COMMIT=fee6f2d0368a7b505d892368f4980ff4e6a5cd45

RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf /afl; \
      echo "[adarare] cloning AFL++ (try $i) ..." >&2; \
      # Reduce payload:
      #  - --filter=blob:none: partial clone (needs git >= 2.19; Ubuntu 20.04+ ok)
      #  - --no-checkout: checkout pinned commit after clone
      if git clone --filter=blob:none --no-checkout "$AFLPP_REPO" /afl; then \
        cd /afl; \
        git checkout -f "$AFLPP_COMMIT"; \
        break; \
      fi; \
      echo "[adarare] clone failed, retrying..." >&2; \
      sleep $((i * 5)); \
    done; \
    test -d /afl/.git

# -----------------------------------------------------------------------------
# Build AFL++ once (no duplicate builds)
# - AFL_NO_X86=1: skip flaky x86 checks
# - CC=clang
# - PYTHON_INCLUDE=/ : keep as you used (but note: AFL++ python optional)
# -----------------------------------------------------------------------------
RUN set -eux; \
    cd /afl; \
    unset CFLAGS CXXFLAGS; \
    export CC=clang AFL_NO_X86=1 PYTHON_INCLUDE=/; \
    make -j"$(nproc)" all; \
    cp utils/aflpp_driver/libAFLDriver.a /
