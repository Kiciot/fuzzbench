# Copyright 2020 Google LLC
ARG parent_image
FROM $parent_image

ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

RUN apt-get update && \
    apt-get install -y \
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
        libgtk-3-dev \
        ninja-build

# 下载 BeliefFuzz
RUN git config --global http.proxy $HTTP_PROXY && \
    git config --global https.proxy $HTTPS_PROXY && \
    git clone --depth 1 https://github.com/5hadowblad3/Belieffuzz /afl

# 编译
RUN cd /afl && \
    unset CFLAGS CXXFLAGS && \
    make -j$(nproc)

# 拷贝 fuzzer 二进制到 OUT（关键）
RUN cp /afl/afl-fuzz /out/afl-fuzz