# Copyright 2016 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

# Keep proxy for curl/git when needed. We will explicitly disable it for apt.
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------------------------------------------------------
# Helper scripts: robust apt + curl
# -----------------------------------------------------------------------------
RUN set -eux; \
  cat > /usr/local/bin/_apt_install <<'EOF'; \
#!/bin/sh
set -eu
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
export DEBIAN_FRONTEND=noninteractive

# robust apt settings
printf '%s\n' \
  'Acquire::Retries "8";' \
  'Acquire::http::Timeout "60";' \
  'Acquire::https::Timeout "60";' \
  'Acquire::http::Pipeline-Depth "0";' \
  'Acquire::https::Pipeline-Depth "0";' \
  'Acquire::https::No-Cache "true";' \
  'Acquire::http::No-Cache "true";' \
  'DPkg::Lock::Timeout "120";' \
  > /etc/apt/apt.conf.d/80-fuzzbench-retries

i=1
while [ "$i" -le 8 ]; do
  apt-get update && \
  apt-get install -y --no-install-recommends --fix-missing "$@" && \
  exit 0
  echo "[apt] failed ($i/8): $*" >&2
  i=$((i+1))
  sleep 5
  apt-get update --fix-missing || true
done
exit 1
EOF
  chmod +x /usr/local/bin/_apt_install; \
  \
  cat > /usr/local/bin/_curl_try <<'EOF'; \
#!/bin/sh
set -eu
out="$1"; shift
rm -f "$out"
for url in "$@"; do
  [ -n "$url" ] || continue
  i=1
  while [ "$i" -le 6 ]; do
    rm -f "$out"
    if curl -fL \
        --retry 12 --retry-connrefused --retry-delay 5 --retry-max-time 600 \
        --connect-timeout 20 --max-time 1200 \
        -o "$out" "$url"; then
      test -s "$out"
      exit 0
    fi
    echo "[curl] failed ($i/6): $url" >&2
    i=$((i+1))
    sleep 5
  done
done
echo "[curl] permanently failed" >&2
exit 1
EOF
  chmod +x /usr/local/bin/_curl_try

# -----------------------------------------------------------------------------
# APT: switch to TUNA mirror and install deps (apt ignores proxy)
# -----------------------------------------------------------------------------
RUN set -eux; \
  for f in /etc/apt/sources.list /etc/apt/sources.list.d/*.list; do \
    [ -f "$f" ] || continue; \
    sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$f" || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' "$f" || true; \
  done; \
  /usr/local/bin/_apt_install \
    ca-certificates \
    curl \
    git \
    make autoconf automake libtool \
    tcl \
    zlib1g-dev \
    zip unzip; \
  rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Fetch sqlite source (try multiple URLs; no git needed)
#   - Primary: sqlite.org tarball endpoint
#   - Fallback1: fossil tarball (same revision)
#   - Fallback2: GitHub mirror (last resort; replace if you have your own mirror)
# -----------------------------------------------------------------------------
RUN set -eux; \
  mkdir -p "$SRC/sqlite3"; \
  cd "$SRC/sqlite3"; \
  /usr/local/bin/_curl_try sqlite3.tar.gz \
    "https://sqlite.org/src/tarball/sqlite.tar.gz?r=c78cbf2e86850cc6" \
    "https://www.sqlite.org/src/tarball/sqlite.tar.gz?r=c78cbf2e86850cc6" \
    "https://sqlite.org/src/tarball/c78cbf2e86850cc6/sqlite.tar.gz" \
  ; \
  tar xzf sqlite3.tar.gz --strip-components 1; \
  rm -f sqlite3.tar.gz

# Build seed corpus safely (avoid xargs weirdness; zip reads from stdin)
RUN set -eux; \
  cd "$SRC/sqlite3"; \
  find . -name "*.test" -print0 | tr '\0' '\n' | zip -q "$SRC/ossfuzz_seed_corpus.zip" -@ || true; \
  test -s "$SRC/ossfuzz_seed_corpus.zip"

WORKDIR $SRC/sqlite3

# Copy build script.
COPY build.sh $SRC/

# Copy dicts if present without failing the build.
# (If your Docker supports BuildKit, this stays fine; if not, it still works.)
RUN set -eux; \
  if ls "$SRC"/*.dict >/dev/null 2>&1; then \
    cp -v "$SRC"/*.dict "$SRC"/; \
  fi