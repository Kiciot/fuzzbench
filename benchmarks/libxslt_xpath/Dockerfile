# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ARG GIT_SSL_NO_VERIFY=1

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT stability: mirror + retries + timeouts
# -----------------------------
RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.edge.kernel.org/ubuntu|g' /etc/apt/sources.list || true; \
    fi; \
    printf 'Acquire::Retries "8";\nAcquire::http::Timeout "60";\nAcquire::https::Timeout "60";\nAcquire::http::Pipeline-Depth "0";\n' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# -----------------------------
# Toolchain versions (manual build)
# -----------------------------
# Need to build M4-1.4.19, autoconf-2.71, automake-1.16.x manually for Ubuntu 20.04-based base images.
ENV M4_VERSION=1.4.19
ENV AUTOCONF_VERSION=2.71
ENV AUTOMAKE_VERSION=1.16.5

# -----------------------------
# Base deps + robust downloads/builds
# -----------------------------
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
        curl \
        git \
        make \
        libtool \
        pkg-config \
        libgcrypt-dev \
      && break; \
      echo "apt-get failed, retry $i/5"; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# -----------------------------
# Git robustness (proxy + optional SSL verify off)
# -----------------------------
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.lowSpeedLimit 1000; \
    git config --global http.lowSpeedTime 60; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    if [ "${GIT_SSL_NO_VERIFY}" = "1" ]; then \
      git config --global http.sslVerify false; \
    fi

# -----------------------------
# Helper: download-with-retry (GNU mirrors sometimes flap behind proxies)
# -----------------------------
RUN set -eux; \
    cat > /usr/local/bin/_dl_retry <<'SH'; \
#!/bin/sh
set -eu
url="$1"
out="$2"
i=1
while [ "$i" -le 8 ]; do
  rm -f "$out"
  if wget -O "$out" --tries=3 --timeout=60 "$url"; then
    exit 0
  fi
  echo "download failed ($i/8): $url"
  i=$((i+1))
  sleep 10
done
echo "download permanently failed: $url" >&2
exit 1
SH
    chmod +x /usr/local/bin/_dl_retry

# -----------------------------
# Build m4
# -----------------------------
RUN set -eux; \
    _dl_retry "https://ftp.gnu.org/gnu/m4/m4-${M4_VERSION}.tar.gz" "/tmp/m4.tar.gz"; \
    tar -C /tmp -xf /tmp/m4.tar.gz; \
    rm -f /tmp/m4.tar.gz; \
    cd "/tmp/m4-${M4_VERSION}"; \
    ./configure; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf "/tmp/m4-${M4_VERSION}"

# -----------------------------
# Build autoconf
# -----------------------------
RUN set -eux; \
    _dl_retry "https://ftp.gnu.org/gnu/autoconf/autoconf-${AUTOCONF_VERSION}.tar.gz" "/tmp/autoconf.tar.gz"; \
    tar -C /tmp -xf /tmp/autoconf.tar.gz; \
    rm -f /tmp/autoconf.tar.gz; \
    cd "/tmp/autoconf-${AUTOCONF_VERSION}"; \
    ./configure; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf "/tmp/autoconf-${AUTOCONF_VERSION}"

# -----------------------------
# Build automake
# -----------------------------
RUN set -eux; \
    _dl_retry "https://ftp.gnu.org/gnu/automake/automake-${AUTOMAKE_VERSION}.tar.gz" "/tmp/automake.tar.gz"; \
    tar -C /tmp -xf /tmp/automake.tar.gz; \
    rm -f /tmp/automake.tar.gz; \
    cd "/tmp/automake-${AUTOMAKE_VERSION}"; \
    ./configure; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf "/tmp/automake-${AUTOMAKE_VERSION}"

# Use the newly installed aclocal macros.
ENV ACLOCAL_PATH='/usr/share/aclocal/'

# -----------------------------
# Fetch sources (with retries)
# -----------------------------
WORKDIR $SRC

# libxml2 pinned commit + libxslt head
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf libxml2; \
      git clone --filter=blob:none https://gitlab.gnome.org/GNOME/libxml2.git libxml2 && break; \
      echo "git clone libxml2 failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d libxml2; \
    cd libxml2; \
    git checkout c7260a47f19e01f4f663b6a56fbdc2dafd8a6e7e

RUN set -eux; \
    for i in 1 2 3 4 5; do \
      rm -rf libxslt; \
      git clone --filter=blob:none https://gitlab.gnome.org/GNOME/libxslt.git libxslt && break; \
      echo "git clone libxslt failed, retry $i/5"; \
      sleep 10; \
    done; \
    test -d libxslt

WORKDIR $SRC/libxslt
COPY build.sh $SRC/