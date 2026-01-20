# Copyright 2016 Google Inc.
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
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

RUN set -eux; \
    apt-get update || (sleep 5 && apt-get update); \
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y || true; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      make autoconf automake libtool \
      curl \
      tcl \
      zlib1g-dev \
      git \
      zip unzip \
    || (sleep 10 && apt-get update --fix-missing && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
          ca-certificates make autoconf automake libtool curl tcl zlib1g-dev git zip unzip); \
    rm -rf /var/lib/apt/lists/*


RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0


RUN set -eux; \
    mkdir -p "$SRC/sqlite3"; \
    cd "$SRC/sqlite3"; \
    curl -fsSL \
      --retry 8 \
      --retry-connrefused \
      --retry-delay 5 \
      --retry-max-time 300 \
      --connect-timeout 20 \
      --max-time 600 \
      'https://sqlite.org/src/tarball/sqlite.tar.gz?r=c78cbf2e86850cc6' \
      -o sqlite3.tar.gz; \
    tar xzf sqlite3.tar.gz --strip-components 1; \
    rm -f sqlite3.tar.gz

RUN set -eux; \
    cd "$SRC/sqlite3"; \
    find . -name "*.test" -print0 | xargs -0 -r zip "$SRC/ossfuzz_seed_corpus.zip"

WORKDIR $SRC/sqlite3
COPY build.sh *.dict $SRC/