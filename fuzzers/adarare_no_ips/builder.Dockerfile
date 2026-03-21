# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# ...

ARG parent_image
FROM $parent_image

ENV DEBIAN_FRONTEND=noninteractive
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

RUN echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential python3-dev python3-setuptools automake cmake git flex bison \
        libglib2.0-dev libpixman-1-dev cargo libgtk-3-dev ninja-build \
        gcc-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-plugin-dev \
        libstdc++-$(gcc --version|head -n1|sed 's/\..*//'|sed 's/.* //')-dev && \
    rm -rf /var/lib/apt/lists/*

RUN git config --global http.proxy http://172.17.0.1:7890 && \
    git config --global http.postBuffer 524288000 && \
    git config --global core.compression 0

RUN for i in 1 2 3; do \
      git clone -b dev https://github.com/Kiciot/AFLplusplus /afl && break || \
      (echo "Clone failed, retrying in 5s..." && sleep 5); \
    done && \
    cd /afl && \
    git checkout 560f635991e66781126d1323edbba5db802f814c

RUN cd /afl && \
    unset CFLAGS CXXFLAGS && \
    export CC=clang AFL_NO_X86=1 && \
    PYTHON_INCLUDE=/ make && \
    cp utils/aflpp_driver/libAFLDriver.a /