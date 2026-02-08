# syntax=docker/dockerfile:1.6
ARG parent_image
FROM ${parent_image}

# 1. 设置 Shell，遇到错误立即退出 (-e)
SHELL ["/bin/bash", "-euxo", "pipefail", "-c"]

# 2. 代理设置 (保留你的逻辑)
ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# 配置 APT 代理
RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    printf 'Acquire::http::Proxy "%s";\nAcquire::https::Proxy "%s";\n' "${HTTP_PROXY}" "${HTTPS_PROXY:-$HTTP_PROXY}" > /etc/apt/apt.conf.d/99proxy; \
  fi && \
  printf 'Acquire::Retries "5";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' > /etc/apt/apt.conf.d/80-retries

# 3. 安装依赖 【关键修正】
# 移除了 clang, clang++, llvm，避免与基础镜像冲突
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      ca-certificates \
      git \
      wget \
      binutils \
      make \
      libc++-dev \
      libc++abi-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. 下载并编译 FairFuzz (AFL-RB)
ARG AFL_RB_COMMIT="e529c1f1b3666ad94e4d6e7ef24ea648aff39ae2"
RUN \
  if [[ -n "${HTTP_PROXY}" ]]; then \
    git config --global http.proxy "${HTTP_PROXY}"; \
  fi && \
  git clone https://github.com/carolemieux/afl-rb.git /afl && \
  cd /afl && \
  git checkout "${AFL_RB_COMMIT}" && \
  # 使用 CC=clang 确保用上基础镜像里的编译器
  CC=clang AFL_NO_X86=1 make clean all

# 5. 下载并编译 AFL Driver
# 【关键修正】确保所有操作都在 /afl 目录下进行，生成的 .a 库路径明确
WORKDIR /afl
ARG LLVM_COMMIT="5feb80e748924606531ba28c97fe65145c65372e"
RUN \
  url="https://raw.githubusercontent.com/llvm/llvm-project/${LLVM_COMMIT}/compiler-rt/lib/fuzzer/afl/afl_driver.cpp"; \
  wget -t 5 -T 30 -O afl_driver.cpp "${url}" && \
  \
  # 编译 AFL 的 LLVM 运行时 (从 afl-rb 源码中)
  clang -Wno-pointer-sign -c llvm_mode/afl-llvm-rt.o.c -I. -o afl-llvm-rt.o && \
  \
  # 编译 Driver
  clang++ -stdlib=libc++ -std=c++11 -O2 -c afl_driver.cpp -o afl_driver.o && \
  \
  # 打包成静态库
  ar r /libAFL.a afl-llvm-rt.o afl_driver.o

# 6. 恢复工作目录 (FuzzBench 规范)
WORKDIR /src