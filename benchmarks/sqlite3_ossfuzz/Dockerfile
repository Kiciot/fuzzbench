# Copyright 2016 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ARG GIT_SSL_NO_VERIFY=0

# Proxy kept for git/curl when needed; APT will explicitly ignore proxy.
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- helper: robust curl download with fallback urls ----
RUN set -eux; \
  cat > /usr/local/bin/_curl_try <<'EOF'; \
#!/bin/sh
set -eu
out="$1"; shift
[ -n "$out" ] || exit 2
rm -f "$out"
for url in "$@"; do
  [ -n "$url" ] || continue
  i=1
  while [ "$i" -le 3 ]; do
    rm -f "$out"
    if curl -fsSL \
        --retry 12 --retry-connrefused --retry-delay 5 --retry-max-time 1200 \
        --connect-timeout 20 --max-time 1200 \
        -o "$out" "$url"; then
      test -s "$out"
      exit 0
    fi
    echo "[curl] failed ($i/3): $url" >&2
    i=$((i+1))
    sleep 5
  done
done
echo "[curl] permanently failed" >&2
exit 1
EOF
  chmod +x /usr/local/bin/_curl_try

# ---- APT: ignore proxy + stable mirror + retries/timeouts ----
RUN set -eux; \
    for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do \
      [ -f "$f" ] || continue; \
      sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$f" || true; \
      sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$f" || true; \
    done; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      'DPkg::Lock::Timeout "120";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries; \
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy; \
    for i in 1 2 3 4 5; do \
      apt-get update && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        make autoconf automake libtool \
        curl \
        tcl \
        zlib1g-dev \
        git \
        zip unzip \
      && break; \
      echo "[apt] failed ($i/5), retry..." >&2; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# ---- Git robustness (for any build steps that use git) ----
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}" || true; \
    git config --global https.proxy "${HTTPS_PROXY}" || true; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    git config --global http.version HTTP/1.1; \
    if [ "${GIT_SSL_NO_VERIFY}" = "1" ]; then \
      git config --global http.sslVerify false; \
    fi

# ---- Fetch sqlite source (tarball) with robust retries + fallback ----
# Primary: sqlite.org tarball. Secondary: optional mirror url (replace with your working mirror if you have one).
RUN set -eux; \
    mkdir -p "$SRC/sqlite3"; \
    cd "$SRC/sqlite3"; \
    /usr/local/bin/_curl_try sqlite3.tar.gz \
      'https://sqlite.org/src/tarball/sqlite.tar.gz?r=c78cbf2e86850cc6' \
      '' \
      ''; \
    tar xzf sqlite3.tar.gz --strip-components 1; \
    rm -f sqlite3.tar.gz

# Build seed corpus safely
RUN set -eux; \
    cd "$SRC/sqlite3"; \
    find . -name "*.test" -print0 | xargs -0 -r -I{} printf '%s\n' "{}" | zip -q "$SRC/ossfuzz_seed_corpus.zip" -@

WORKDIR $SRC/sqlite3

# Avoid wildcard COPY trap: copy build.sh always; dict is optional.
COPY build.sh $SRC/
# If you DO have dict files, keep this. If not, delete the next line.
COPY ./*.dict $SRC/