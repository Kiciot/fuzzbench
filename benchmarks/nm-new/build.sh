#!/bin/bash -eu
# Copyright 2019 Google Inc.
# Licensed under the Apache License, Version 2.0

# FuzzBench 会设置 OUT / CC / CXX / CFLAGS / CXXFLAGS 等
# 我们只做最小增补，避免老代码的 -Werror 把编译卡死
export CFLAGS="${CFLAGS:-} -Wno-error -Wno-deprecated -Wno-unused-variable"
export CXXFLAGS="${CXXFLAGS:-} -Wno-error -Wno-deprecated -Wno-unused-variable"

BINUTILS_VER="2.26"
WORK="/tmp/binutils_work"
SRC_TAR="binutils-${BINUTILS_VER}.tar.gz"
SRC_URL1="https://ftp.gnu.org/gnu/binutils/${SRC_TAR}"
SRC_URL2="https://mirrors.edge.kernel.org/gnu/binutils/${SRC_TAR}"

mkdir -p "${WORK}"
cd "${WORK}"

download() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 8 --retry-connrefused --retry-delay 3 --connect-timeout 20 --max-time 600 -o "${SRC_TAR}" "${url}"
    return 0
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -O "${SRC_TAR}" --tries=8 --timeout=60 "${url}"
    return 0
  fi
  echo "need curl or wget" >&2
  exit 2
}

if [ ! -f "${SRC_TAR}" ]; then
  ( download "${SRC_URL1}" ) || ( rm -f "${SRC_TAR}" && download "${SRC_URL2}" )
fi

rm -rf "${WORK}/src" "${WORK}/build"
mkdir -p "${WORK}/src" "${WORK}/build"
tar -xf "${SRC_TAR}" -C "${WORK}/src" --strip-components=1

# out-of-tree build：configure 要从源码目录调用
cd "${WORK}/build"
"${WORK}/src/configure" \
  --disable-shared \
  --disable-gdb \
  --disable-libdecnumber \
  --disable-readline \
  --disable-sim \
  --disable-werror

make -j"$(nproc)"

# nm-new 一般会在 build/binutils/ 里
cp -f "${WORK}/build/binutils/nm-new" "${OUT}/nm-new"

# ---- seeds ----
SEED_DIR="${OUT}/seeds"
mkdir -p "${SEED_DIR}"

# 避免 find|head 触发 SIGPIPE(141)：用计数 + break，并吞掉 SIGPIPE
n=0
while IFS= read -r f; do
  cp -f "$f" "${SEED_DIR}/" || true
  n=$((n+1))
  [ "$n" -ge 100 ] && break
done < <(find "${WORK}/build" -name '*.o' -type f -print) || true

# zip 可能不存在；FuzzBench 的基础镜像一般有 zip，但这里做个兜底
if command -v zip >/dev/null 2>&1; then
  zip -j "${OUT}/nm-new_seed_corpus.zip" "${SEED_DIR}"/* >/dev/null 2>&1 || true
else
  # 没有 zip 就打包成 tar.gz（不会影响你本地调试，但 FuzzBench 可能更偏好 zip）
  tar -czf "${OUT}/nm-new_seed_corpus.tar.gz" -C "${SEED_DIR}" . || true
fi

rm -rf "${SEED_DIR}"