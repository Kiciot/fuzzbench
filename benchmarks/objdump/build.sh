#!/usr/bin/env bash
set -euxo pipefail

# ---- config ----
BINUTILS_VER="${BINUTILS_VER:-2.28}"
TARBALL="binutils-${BINUTILS_VER}.tar.gz"

# FuzzBench 会提供 OUT/CFLAGS/CXXFLAGS；这里做一下兜底避免 -u 触发未定义
OUT="${OUT:?OUT is not set}"
CFLAGS="${CFLAGS:-}"
CXXFLAGS="${CXXFLAGS:-}"

# 显式放宽一些警告（避免老代码在新编译器下被 -Werror 卡死）
export CFLAGS="${CFLAGS} -Wno-error -Wno-deprecated -Wno-unused-variable"
export CXXFLAGS="${CXXFLAGS} -Wno-error -Wno-deprecated -Wno-unused-variable"

# ---- helper: download ----
dl() {
  local out="$1"; shift
  # 优先用你镜像里已有的 _dl_retry（你前面 Dockerfile 里就是这么装的）
  if command -v _dl_retry >/dev/null 2>&1; then
    # 约定：_dl_retry <url1> [url2] [url3] <out>
    _dl_retry "$1" "${2:-}" "${3:-}" "$out"
    return 0
  fi

  # 兜底：curl 直连下载
  curl -fL --retry 8 --retry-delay 3 --connect-timeout 20 --max-time 600 -o "$out" "$1"
}

# ---- get source ----
WORK="/tmp/binutils_work"
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"

# 如果你的镜像里已经把源码放在 /src/binutils，也可以直接复用（避免重复下载）
if [ -f "/src/binutils/configure" ]; then
  SRC_DIR="/src/binutils"
else
  dl "$WORK/$TARBALL" \
    "https://ftp.gnu.org/gnu/binutils/${TARBALL}" \
    "https://ftpmirror.gnu.org/gnu/binutils/${TARBALL}" \
    "https://mirrors.kernel.org/gnu/binutils/${TARBALL}"
  tar -xf "$WORK/$TARBALL"
  SRC_DIR="$WORK/binutils-${BINUTILS_VER}"
fi

# ---- build (out-of-tree，避免污染源码目录) ----
BUILD_DIR="$WORK/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

"$SRC_DIR/configure" \
  --disable-shared \
  --disable-gdb \
  --disable-libdecnumber \
  --disable-readline \
  --disable-sim \
  --disable-werror \
  --disable-nls

make -j"$(nproc)"

# ---- install target binary into OUT ----
mkdir -p "$OUT"
cp -f "$BUILD_DIR/binutils/objdump" "$OUT/objdump"

# ---- seed corpus ----
SEED_DIR="$OUT/seeds"
rm -rf "$SEED_DIR"
mkdir -p "$SEED_DIR"

# 用 .o 文件做种子（你原逻辑保留），并避免 xargs 空输入导致失败
find "$BUILD_DIR" -name "*.o" -print | head -n 100 | while read -r f; do
  cp -f "$f" "$SEED_DIR/" || true
done

# 允许 seeds 为空时 zip 不致命
if ls -1 "$SEED_DIR"/* >/dev/null 2>&1; then
  zip -j "$OUT/objdump_seed_corpus.zip" "$SEED_DIR"/* >/dev/null
else
  # 至少生成一个空 zip，避免下游依赖文件存在
  (cd "$SEED_DIR" && zip -j "$OUT/objdump_seed_corpus.zip" . >/dev/null) || true
fi

rm -rf "$SEED_DIR"