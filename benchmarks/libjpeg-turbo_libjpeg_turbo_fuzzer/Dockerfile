FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# 1. APT 阶段：使用国内镜像源，并显式禁用代理。
# 这里不要让 apt 走代理，避免 502 / TLS 中断。
RUN set -eux; \
    sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list || true; \
    sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list || true; \
    printf '%s\n' \
      'Acquire::Retries "8";' \
      'Acquire::http::Timeout "60";' \
      'Acquire::https::Timeout "60";' \
      'Acquire::http::Pipeline-Depth "0";' \
      'Acquire::https::Pipeline-Depth "0";' \
      'Acquire::ForceIPv4 "true";' \
      'Acquire::http::Proxy "false";' \
      'Acquire::https::Proxy "false";' \
      > /etc/apt/apt.conf.d/80-local-mirror-no-proxy; \
    env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
      apt-get update; \
    env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        make \
        yasm \
        cmake; \
    rm -rf /var/lib/apt/lists/*

# 2. APT 完成后，再给 git / curl / 其他下载工具注入代理。
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# 3. Git 网络鲁棒性配置。
RUN set -eux; \
    git config --global http.proxy "${HTTP_PROXY}"; \
    git config --global https.proxy "${HTTPS_PROXY}"; \
    git config --global http.version HTTP/1.1; \
    git config --global http.lowSpeedLimit 1; \
    git config --global http.lowSpeedTime 600; \
    git config --global http.postBuffer 524288000; \
    git config --global core.compression 0; \
    git config --global pack.threads 1; \
    git config --global http.maxRequests 4

# 4. 通用 git 重试脚本。
RUN set -eux; \
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      'set -euo pipefail' \
      'n="${GIT_RETRY_N:-8}"' \
      'sleep_s="${GIT_RETRY_SLEEP:-10}"' \
      'i=1' \
      'while true; do' \
      '  if "$@"; then' \
      '    exit 0' \
      '  fi' \
      '  if [ "$i" -ge "$n" ]; then' \
      '    echo "[git_retry] failed after ${n} attempts: $*" >&2' \
      '    exit 1' \
      '  fi' \
      '  echo "[git_retry] attempt ${i} failed; retrying in ${sleep_s}s: $*" >&2' \
      '  sleep "${sleep_s}"' \
      '  i=$((i+1))' \
      'done' \
      > /usr/local/bin/git_retry; \
    chmod +x /usr/local/bin/git_retry

# 5. 拉取 libjpeg-turbo fuzz 仓库和多个分支。
# 原始 Dockerfile 在这里容易因 GitHub TLS/RPC 中断失败，所以改成浅克隆 + 单分支 + 重试。
RUN set -eux; \
    git_retry git clone --depth 1 https://github.com/libjpeg-turbo/fuzz; \
    cat fuzz/branches.txt | while read branch; do \
      [ -n "$branch" ] || continue; \
      rm -rf "libjpeg-turbo.$branch"; \
      git_retry git clone \
        --depth 1 \
        --single-branch \
        -b "$branch" \
        https://github.com/libjpeg-turbo/libjpeg-turbo \
        "libjpeg-turbo.$branch"; \
    done

# 6. 拉取 seed corpus：这里不能浅克隆，因为后面要 checkout 固定历史 commit。
RUN set -eux; \
    git_retry git clone https://github.com/libjpeg-turbo/seed-corpora; \
    git -C seed-corpora checkout 7c9ea5ffaac76ef618657978c9fdfa845d310b93

RUN set -eux; \
    cd seed-corpora; \
    zip -r ../decompress_fuzzer_seed_corpus.zip \
        afl-testcases/jpeg* \
        bugs/decompress* \
        "$SRC"/libjpeg-turbo/testimages/*.jpg

RUN set -eux; \
    cd seed-corpora; \
    zip -r ../compress_fuzzer_seed_corpus.zip \
        afl-testcases/bmp \
        afl-testcases/gif* \
        bugs/compress* \
        "$SRC"/libjpeg-turbo/testimages/*.bmp \
        "$SRC"/libjpeg-turbo/testimages/*.ppm

RUN rm -rf seed-corpora

COPY build.sh $SRC/