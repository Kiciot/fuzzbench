# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# ...

ARG parent_image
FROM $parent_image

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list || true; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Proxy "false";' \
      'Acquire::https::Proxy "false";' \
      > /etc/apt/apt.conf.d/80-retries; \
    apt-get update && \
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
        gcc-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-plugin-dev \
        libstdc++-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-dev && \
    rm -rf /var/lib/apt/lists/*


RUN for i in 1 2 3; do \
      git clone https://github.com/Kiciot/AFLplusplus /afl && break || \
      (echo "Clone failed, retrying in 5s..." && sleep 5); \
    done && \
    cd /afl && \
    git checkout 5bb02fa6c173f10711daaeb7db394aadd61ca191

RUN cd /afl && \
    unset CFLAGS CXXFLAGS && \
    export CC=clang AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make && \
    cp utils/aflpp_driver/libAFLDriver.a /
