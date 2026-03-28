# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

# Proxy only for git/curl/wget as needed; APT will be forced to ignore it.
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- Helpers: robust retry wrappers ----
RUN set -eux; \
  cat > /usr/local/bin/_retry <<'EOF'; \
#!/bin/sh
set -eu
n="${1:-5}"; shift || true
i=1
while [ "$i" -le "$n" ]; do
  if sh -c "$*"; then exit 0; fi
  echo "[retry] failed ($i/$n): $*" >&2
  i=$((i+1))
  sleep 5
done
exit 1
EOF
  chmod +x /usr/local/bin/_retry; \
  \
  cat > /usr/local/bin/_apt_install <<'EOF'; \
#!/bin/sh
set -eu
# Force APT to ignore any proxy envs.
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export DEBIAN_FRONTEND=noninteractive
# retries/timeouts
printf '%s\n' \
  'Acquire::Retries "8";' \
  'Acquire::http::Timeout "60";' \
  'Acquire::https::Timeout "60";' \
  'Acquire::http::Pipeline-Depth "0";' \
  'Acquire::https::Pipeline-Depth "0";' \
  'DPkg::Lock::Timeout "120";' \
  > /etc/apt/apt.conf.d/80-fuzzbench-retries
# update + install with retries
i=1
while [ "$i" -le 8 ]; do
  apt-get update && \
  apt-get install -y --no-install-recommends --fix-missing "$@" && \
  exit 0
  echo "[apt] install failed ($i/8): $*" >&2
  i=$((i+1))
  sleep 5
  apt-get update --fix-missing || true
done
exit 1
EOF
  chmod +x /usr/local/bin/_apt_install; \
  \
  cat > /usr/local/bin/_git_clone <<'EOF'; \
#!/bin/sh
set -eu
url="$1"; dir="$2"
rm -rf "$dir"
# Harden git for slow/unstable links.
git config --global http.proxy "${HTTP_PROXY:-}" || true
git config --global https.proxy "${HTTPS_PROXY:-}" || true
git config --global http.lowSpeedLimit 1 || true
git config --global http.lowSpeedTime 600 || true
git config --global http.postBuffer 524288000 || true
git config --global core.compression 0 || true
git config --global http.version HTTP/1.1 || true

i=1
while [ "$i" -le 5 ]; do
  rm -rf "$dir"
  if git clone --depth 1 --filter=blob:none "$url" "$dir"; then
    exit 0
  fi
  echo "[git] clone failed ($i/5): $url -> $dir" >&2
  i=$((i+1))
  sleep 5
done
exit 1
EOF
  chmod +x /usr/local/bin/_git_clone; \
  \
  cat > /usr/local/bin/_curl_dl <<'EOF'; \
#!/bin/sh
set -eu
url="$1"; out="$2"
rm -f "$out"
i=1
while [ "$i" -le 5 ]; do
  rm -f "$out"
  if curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 \
      --connect-timeout 20 --max-time 600 \
      -o "$out" "$url"; then
    test -s "$out"
    exit 0
  fi
  echo "[curl] download failed ($i/5): $url" >&2
  i=$((i+1))
  sleep 5
done
exit 1
EOF
  chmod +x /usr/local/bin/_curl_dl

# ---- APT: switch to TUNA mirror, but force apt to ignore proxy ----
RUN set -eux; \
  if [ -f /etc/apt/sources.list ]; then \
    sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
  fi; \
  /usr/local/bin/_apt_install \
    ca-certificates git wget curl xz-utils \
    make autoconf automake libtool pkg-config

WORKDIR $SRC

# 1) freetype
RUN set -eux; \
  /usr/local/bin/_git_clone https://github.com/freetype/freetype.git freetype2

# 2) text-rendering-tests (TRT)
RUN set -eux; \
  /usr/local/bin/_git_clone https://github.com/unicode-org/text-rendering-tests.git TRT

# 3) libarchive tarball (use curl wrapper; much more resilient than wget here)
RUN set -eux; \
  /usr/local/bin/_curl_dl \
    "https://github.com/libarchive/libarchive/releases/download/v3.4.3/libarchive-3.4.3.tar.xz" \
    "libarchive-3.4.3.tar.xz"

# Your project files
COPY . $SRC/