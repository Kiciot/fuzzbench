# Copyright 2020 Google LLC
# ... (版权声明省略) ...

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# === 网络/代理 终极配置 ===
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16

ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# 1. 强制 Git 使用代理
# 2. 关闭 SSL 验证 (防止代理证书报错)
# 3. 增大 buffer 防止大文件中断
RUN git config --global http.proxy http://172.17.0.1:7890 && \
    git config --global http.sslVerify false && \
    git config --global http.postBuffer 524288000
# ========================

RUN apt-get update && \
    apt-get install -y \
    make \
    autoconf \
    automake \
    libtool \
    zlib1g-dev

# zlib 之前是成功的，保持不变
RUN git clone \
        --depth 1 \
        --branch v1.2.13 \
        https://github.com/madler/zlib.git

# === 关键修改：给 libpng 加上 --depth 1 ===
RUN git clone \
        --depth 1 \
        https://github.com/glennrp/libpng.git

# 调试命令：如果 CP 失败，这行命令会在构建日志里告诉我们 libpng 里面到底有啥
RUN ls -R libpng/contrib || echo "Directory missing!"

RUN cp libpng/contrib/oss-fuzz/build.sh $SRC

WORKDIR libpng

# 给 wget 也加上代理参数（双重保险）
RUN wget --no-check-certificate -e use_proxy=yes -e http_proxy=172.17.0.1:7890 -qO $OUT/libpng_read_fuzzer.dict \
    https://raw.githubusercontent.com/google/fuzzing/master/dictionaries/png.dict

ADD seeds /opt/seeds
COPY * $SRC/