ARG parent_image
# 通常 FuzzBench 会传入 gcr.io/fuzzbench/builders/benchmark-builder
FROM $parent_image

# ==========================================
# 1. 代理设置 (保留你的配置)
# ==========================================
ARG PROXY=http://172.17.0.1:7890
ENV HTTP_PROXY=${PROXY} HTTPS_PROXY=${PROXY} http_proxy=${PROXY} https_proxy=${PROXY} \
    NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16 no_proxy=localhost,127.0.0.1,::1,172.17.0.0/16

# ==========================================
# 2. 安装依赖
# ==========================================
# 既然使用内置 LibFuzzer，通常不需要额外安装什么。
# 但为了保险起见，保留基础工具。
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git curl \
 && rm -rf /var/lib/apt/lists/*

# 不需要手动 git clone llvm-project
# 不需要手动编译 .a 文件
# 现在的 Clang 已经内置了 Entropic