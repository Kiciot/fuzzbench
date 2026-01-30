FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

# ---- proxy (optional) ----
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY=localhost,127.0.0.1,::1

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

RUN apt-get update && apt-get install -y build-essential make curl wget git

# Install pinned cmake.
RUN wget https://github.com/Kitware/CMake/releases/download/v3.14.5/cmake-3.14.5-Linux-x86_64.sh && \
    chmod +x cmake-3.14.5-Linux-x86_64.sh && \
    ./cmake-3.14.5-Linux-x86_64.sh --skip-license --prefix="/usr/local"

RUN git clone https://github.com/open-source-parsers/jsoncpp
WORKDIR jsoncpp

COPY build.sh $SRC/