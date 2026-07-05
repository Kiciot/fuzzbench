# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ---- optional proxy/mirror for network fetches ----
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=localhost,127.0.0.1,::1
ARG UBUNTU_APT_MIRROR=
ARG UBUNTU_SECURITY_APT_MIRROR=
ARG GIT_CLONE_RETRIES=6
ARG LCMS_COMMIT=f0d963261b28253999e239a844ac74d5a8960f40

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- apt: optional mirror + retries ----
RUN set -eux; \
  if [ -n "${UBUNTU_APT_MIRROR}" ]; then \
    security_mirror="${UBUNTU_SECURITY_APT_MIRROR:-${UBUNTU_APT_MIRROR}}"; \
    sed -i "s|http://archive.ubuntu.com/ubuntu|${UBUNTU_APT_MIRROR}|g" /etc/apt/sources.list || true; \
    sed -i "s|http://security.ubuntu.com/ubuntu|${security_mirror}|g" /etc/apt/sources.list || true; \
  fi; \
  printf '%s\n' \
    'Acquire::Retries "8";' \
    'Acquire::http::Timeout "60";' \
    'Acquire::https::Timeout "60";' \
    'Acquire::http::Pipeline-Depth "0";' \
    'Acquire::https::Pipeline-Depth "0";' \
    > /etc/apt/apt.conf.d/80-retries; \
  apt-get update; \
  apt-get install -y --no-install-recommends \
    make automake libtool wget ca-certificates git; \
  rm -rf /var/lib/apt/lists/*

# ---- git robust ----
RUN set -eux; \
  if [ -n "${HTTP_PROXY}" ]; then git config --global http.proxy "$HTTP_PROXY"; fi; \
  if [ -n "${HTTPS_PROXY}" ]; then git config --global https.proxy "$HTTPS_PROXY"; fi; \
  git config --global http.lowSpeedLimit 1; \
  git config --global http.lowSpeedTime 120; \
  git config --global http.postBuffer 524288000

# pin repo (same commit as benchmark.yaml)
RUN set -eux; \
  rm -rf /src/Little-CMS; \
  git init /src/Little-CMS; \
  git -C /src/Little-CMS remote add origin https://github.com/mm2/Little-CMS.git; \
  ok=0; \
  for i in $(seq 1 "${GIT_CLONE_RETRIES}"); do \
    if git -C /src/Little-CMS fetch --depth 1 origin "${LCMS_COMMIT}"; then \
      ok=1; \
      break; \
    fi; \
    echo "Little-CMS fetch failed (${i}/${GIT_CLONE_RETRIES}), retrying" >&2; \
    sleep 10; \
  done; \
  [ "${ok}" = "1" ]; \
  git -C /src/Little-CMS checkout -f FETCH_HEAD; \
  rm -f /src/Little-CMS/.git/shallow; \
  test "$(git -C /src/Little-CMS rev-parse HEAD)" = "${LCMS_COMMIT}"

RUN set -eux; \
  wget -qO /out/cms_transform_fuzzer.dict \
    https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/icc.dict

COPY cms_transform_fuzzer.cc build.sh /src/
ADD seeds /opt/seeds