# 使用 FuzzBench 标准基础镜像
FROM gcr.io/fuzzbench/base-builder
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY
# 安装编译依赖
# 注意：旧版 binutils 对 texinfo/bison 版本可能敏感，但基础镜像里的通常能用
RUN apt-get update && apt-get install -y \
    flex \
    bison \
    texinfo \
    && rm -rf /var/lib/apt/lists/*

# 拉取源码
RUN git config --global http.proxy http://172.17.0.1:7890
RUN git clone git://sourceware.org/git/binutils-gdb.git

WORKDIR binutils-gdb

# 关键修改：切换到 2.28 版本的官方 Tag
# binutils 的 tag 命名习惯是 binutils-X_XX
RUN git checkout binutils-2_28

# 复制构建脚本
COPY build.sh $SRC/