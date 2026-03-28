# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0
################################################################################

FROM gcr.io/oss-fuzz-base/base-builder@sha256:87ca1e9e19235e731fac8de8d1892ebe8d55caf18e7aa131346fc582a2034fdd

ARG HTTP_PROXY="http://172.17.0.1:7890"
ARG HTTPS_PROXY="http://172.17.0.1:7890"
ARG NO_PROXY="localhost,127.0.0.1,::1,172.17.0.0/16"

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY}

# ---- Helpers ----
RUN set -eux; \
  cat > /usr/local/bin/_retry <<'EOF'\n\
#!/bin/sh\n\
set -eu\n\
n=\"${1:-6}\"; shift || true\n\
i=1\n\
while [ \"$i\" -le \"$n\" ]; do\n\
  if sh -c \"$*\"; then exit 0; fi\n\
  echo \"[retry] failed ($i/$n): $*\" >&2\n\
  i=$((i+1))\n\
  sleep $((i*i))\n\
done\n\
exit 1\n\
EOF\n\
  chmod +x /usr/local/bin/_retry; \
  \
  cat > /usr/local/bin/_apt_install <<'EOF'\n\
#!/bin/sh\n\
set -eu\n\
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy\n\
export DEBIAN_FRONTEND=noninteractive\n\
printf '%s\\n' \\\n\
  'Acquire::Retries \"8\";' \\\n\
  'Acquire::http::Timeout \"60\";' \\\n\
  'Acquire::https::Timeout \"60\";' \\\n\
  'Acquire::http::Pipeline-Depth \"0\";' \\\n\
  'Acquire::https::Pipeline-Depth \"0\";' \\\n\
  'DPkg::Lock::Timeout \"120\";' \\\n\
  > /etc/apt/apt.conf.d/80-fuzzbench-retries\n\
i=1\n\
while [ \"$i\" -le 8 ]; do\n\
  apt-get update && \\\n\
  apt-get install -y --no-install-recommends --fix-missing \"$@\" && \\\n\
  exit 0\n\
  echo \"[apt] install failed ($i/8): $*\" >&2\n\
  i=$((i+1))\n\
  sleep 5\n\
  apt-get update --fix-missing || true\n\
done\n\
exit 1\n\
EOF\n\
  chmod +x /usr/local/bin/_apt_install; \
  \
  cat > /usr/local/bin/_git_fetch_checkout <<'EOF'\n\
#!/bin/sh\n\
set -eu\n\
url=\"$1\"; dir=\"$2\"; ref=\"$3\"\n\
rm -rf \"$dir\" && mkdir -p \"$dir\"\n\
git config --global http.proxy \"${HTTP_PROXY:-}\" || true\n\
git config --global https.proxy \"${HTTPS_PROXY:-}\" || true\n\
git config --global http.lowSpeedLimit 1 || true\n\
git config --global http.lowSpeedTime 600 || true\n\
git config --global http.postBuffer 524288000 || true\n\
git config --global core.compression 0 || true\n\
git config --global http.version HTTP/1.1 || true\n\
i=1\n\
while [ \"$i\" -le 6 ]; do\n\
  rm -rf \"$dir\" && mkdir -p \"$dir\"\n\
  git init \"$dir\" >/dev/null\n\
  git -C \"$dir\" remote add origin \"$url\" >/dev/null\n\
  # 关键：只抓一个 ref，且尽量减少对象体积\n\
  if git -C \"$dir\" fetch --depth 1 --filter=blob:none origin \"$ref\"; then\n\
    git -C \"$dir\" checkout -f FETCH_HEAD >/dev/null\n\
    exit 0\n\
  fi\n\
  echo \"[git] fetch failed ($i/6): $url $ref\" >&2\n\
  i=$((i+1))\n\
  sleep $((i*i))\n\
done\n\
exit 1\n\
EOF\n\
  chmod +x /usr/local/bin/_git_fetch_checkout; \
  \
  cat > /usr/local/bin/_curl_dl <<'EOF'\n\
#!/bin/sh\n\
set -eu\n\
url1=\"$1\"; url2=\"${2:-}\"; url3=\"${3:-}\"; out=\"$4\"\n\
[ -n \"$url1\" ] && [ -n \"$out\" ] || { echo \"usage: _curl_dl <url1> [url2] [url3] <out>\" >&2; exit 2; }\n\
try_one() {\n\
  url=\"$1\"\n\
  [ -n \"$url\" ] || return 1\n\
  rm -f \"$out\"\n\
  curl -fL --retry 8 --retry-connrefused --retry-delay 5 --retry-max-time 300 \\\n\
       --connect-timeout 20 --max-time 600 \\\n\
       -o \"$out\" \"$url\" && test -s \"$out\"\n\
}\n\
for url in \"$url1\" \"$url2\" \"$url3\"; do\n\
  i=1\n\
  while [ \"$i\" -le 3 ]; do\n\
    if try_one \"$url\"; then exit 0; fi\n\
    echo \"[curl] failed ($i/3): $url\" >&2\n\
    i=$((i+1))\n\
    sleep 3\n\
  done\n\
done\n\
echo \"download permanently failed (all mirrors): $url1\" >&2\n\
exit 1\n\
EOF\n\
  chmod +x /usr/local/bin/_curl_dl

# ---- APT (force ignore proxy) ----
RUN set -eux; \
  sed -i 's|http://archive.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
  sed -i 's|http://security.ubuntu.com/ubuntu|http://mirrors.tuna.tsinghua.edu.cn/ubuntu|g' /etc/apt/sources.list || true; \
  /usr/local/bin/_apt_install \
    ca-certificates git curl xz-utils \
    make autoconf automake libtool pkg-config

WORKDIR $SRC

# 1) freetype (默认抓 HEAD；如果你想锁 commit，就把第三参换成具体 commit)
RUN set -eux; \
  /usr/local/bin/_git_fetch_checkout https://github.com/freetype/freetype.git freetype2 HEAD

# 2) TRT
RUN set -eux; \
  /usr/local/bin/_git_fetch_checkout https://github.com/unicode-org/text-rendering-tests.git TRT HEAD

# 3) libarchive tarball (github + 镜像 fallback 示例，第二/第三 URL 你可以换成自己可用的镜像)
RUN set -eux; \
  /usr/local/bin/_curl_dl \
    "https://github.com/libarchive/libarchive/releases/download/v3.4.3/libarchive-3.4.3.tar.xz" \
    "https://registry.npmmirror.com/-/binary/libarchive/3.4.3/libarchive-3.4.3.tar.xz" \
    "" \
    "libarchive-3.4.3.tar.xz"

COPY . $SRC/