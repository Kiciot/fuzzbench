# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# http://www.apache.org/licenses/LICENSE-2.0

ARG parent_image
FROM ${parent_image}

ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
      build-essential \
      clang \
      llvm \
      llvm-dev \
      libc++-dev \
      libc++abi-dev \
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
      libstdc++-$(gcc --version | head -n1 | sed 's/\..*//' | sed 's/.* //')-dev && \
    rm -rf /var/lib/apt/lists/*

RUN git config --global http.proxy "${HTTP_PROXY}" && \
    git config --global https.proxy "${HTTPS_PROXY}"

RUN git clone https://github.com/bitsecurerlab/aflplusplus-hier /afl

ENV CC=clang
ENV CXX=clang++
ENV AFL_SKIP_CPUFREQ=1
ENV AFL_NO_X86=1

RUN cd /afl && \
    unset CFLAGS CXXFLAGS CPPFLAGS && \
    make clean || true && \
    make -j"$(nproc)" && \
    cp utils/aflpp_driver/libAFLDriver.a /

# 可选：快速验一下 wrapper 是否真的能工作
RUN echo 'int main(void){return 0;}' > /tmp/test.c && \
    /afl/afl-clang-fast /tmp/test.c -o /tmp/test_bin && \
    /tmp/test_bin