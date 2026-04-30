FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# 1. 替换为国内镜像源，并强制 apt-get 运行时不走代理（置空环境变量）
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    http_proxy="" https_proxy="" apt-get update && \
    http_proxy="" https_proxy="" apt-get install -y make yasm cmake

# 2. apt 依赖安装完毕后，再注入全局代理环境变量，供给后续的 git 和 curl 使用
ENV HTTP_PROXY=http://172.17.0.1:7890
ENV HTTPS_PROXY=http://172.17.0.1:7890
ENV NO_PROXY=localhost,127.0.0.1,::1,172.17.0.0/16
ENV http_proxy=$HTTP_PROXY
ENV https_proxy=$HTTPS_PROXY
ENV no_proxy=$NO_PROXY

# 3. 显式配置 git 代理（双重保险）
RUN git config --global http.proxy http://172.17.0.1:7890

# 4. 后续拉取代码的逻辑保持不变
RUN git clone https://github.com/libjpeg-turbo/fuzz && \
    cat fuzz/branches.txt | while read branch; do \
      git clone https://github.com/libjpeg-turbo/libjpeg-turbo \
          -b $branch libjpeg-turbo.$branch; \
    done

RUN git clone https://github.com/libjpeg-turbo/seed-corpora && \
    git -C seed-corpora checkout 7c9ea5ffaac76ef618657978c9fdfa845d310b93
RUN cd seed-corpora && \
    zip -r ../decompress_fuzzer_seed_corpus.zip \
        afl-testcases/jpeg* \
        bugs/decompress* \
        $SRC/libjpeg-turbo/testimages/*.jpg
RUN cd seed-corpora && \
    zip -r ../compress_fuzzer_seed_corpus.zip \
        afl-testcases/bmp \
        afl-testcases/gif* \
        bugs/compress* \
        $SRC/libjpeg-turbo/testimages/*.bmp \
        $SRC/libjpeg-turbo/testimages/*.ppm
RUN rm -rf seed-corpora

COPY build.sh $SRC/