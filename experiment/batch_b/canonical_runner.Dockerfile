# Copyright 2026
# Licensed under the Apache License, Version 2.0
#
# Batch B runner assembly with an explicit canonical benchmark-artifact input.
# Runtime variant differences remain in each variant's runner.Dockerfile; this
# file only changes the source of /out/.

ARG canonical_builder_image
ARG parent_runner_image
ARG fuzzer
ARG benchmark
ARG image_namespace=gcr.io/fuzzbench

FROM ${canonical_builder_image} AS builder

FROM ${parent_runner_image}

ARG fuzzer
ARG benchmark
ARG image_namespace=gcr.io/fuzzbench

# -----------------------------
# Proxy (build-time configurable)
# -----------------------------
ARG HTTP_PROXY=http://172.17.0.1:7890
ARG HTTPS_PROXY=http://172.17.0.1:7890
ARG NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

# We use Docker's multi-stage build feature to create a minimal runner image,
# separate from the sometimes bulky builder images.
#
# The builder stage is the one canonical artifact for this benchmark. The
# parent runner is variant-specific and carries only its existing ENV setup.

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# -----------------------------
# APT robustness (retries/timeouts)
# -----------------------------
RUN set -eux; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      > /etc/apt/apt.conf.d/80-fuzzbench-retries

# Install runtime dependencies for benchmarks (retry loop for proxy flakiness).
RUN set -eux; \
    for i in 1 2 3 4 5 6 7 8; do \
      apt-get update -y && \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libxml2 \
        libarchive13 \
        libgss3 \
      && break; \
      echo "apt-get failed ($i/8), retrying..."; \
      sleep 10; \
      apt-get update --fix-missing || true; \
    done; \
    rm -rf /var/lib/apt/lists/*

# Set up the directory for the build artifacts.
ENV OUT=/out
ENV WORKDIR=/out

RUN mkdir -p "$WORKDIR"
WORKDIR "$WORKDIR"

ENV ROOT_DIR=/src

# Copy exactly the artifacts built once for this benchmark. This includes the
# target, CmpLog target, generated dictionary, and initial corpus.
COPY --from=builder /out/ ./

# Copy the source code needed by the normal FuzzBench runner.
COPY benchmarks $ROOT_DIR/benchmarks
COPY fuzzers $ROOT_DIR/fuzzers

ENV SEED_CORPUS_DIR=$WORKDIR/seeds
ENV OUTPUT_CORPUS_DIR=$WORKDIR/corpus

RUN mkdir -p "$SEED_CORPUS_DIR" "$OUTPUT_CORPUS_DIR"

COPY common $ROOT_DIR/common
COPY experiment/runner.py $ROOT_DIR/experiment/runner.py
COPY docker/benchmark-runner $ROOT_DIR/docker/benchmark-runner

ENV PYTHONPATH=$ROOT_DIR
RUN chmod +x $ROOT_DIR/docker/benchmark-runner/startup-runner.sh
ENTRYPOINT $ROOT_DIR/docker/benchmark-runner/startup-runner.sh
