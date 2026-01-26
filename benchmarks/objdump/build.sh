#!/usr/bin/env bash
set -euxo pipefail

# ---- config ----
BINUTILS_VER="${BINUTILS_VER:-2.28}"
TARBALL="binutils-${BINUTILS_VER}.tar.gz"

# FuzzBench will set OUT/CC/CXX/CFLAGS/CXXFLAGS. Enforce the critical ones.
OUT="${OUT:?OUT is not set}"
: "${CC:?CC is not set}"
: "${CXX:?CXX is not set}"
CFLAGS="${CFLAGS:-}"
CXXFLAGS="${CXXFLAGS:-}"

# If AFL++ wrappers exist in the image, force them.
# This is required because the sanity check below expects AFL markers.
if command -v afl-clang-fast >/dev/null 2>&1 && command -v afl-clang-fast++ >/dev/null 2>&1; then
  export CC=afl-clang-fast
  export CXX=afl-clang-fast++
fi

# Relax some warnings (older code + newer compilers)
export CFLAGS="${CFLAGS} -Wno-error -Wno-deprecated -Wno-unused-variable"
export CXXFLAGS="${CXXFLAGS} -Wno-error -Wno-deprecated -Wno-unused-variable"

# For large autotools projects (binutils), also pin build/host compilers to avoid
# silently falling back to system gcc and losing instrumentation.
export CC_FOR_BUILD="$CC"
export CXX_FOR_BUILD="$CXX"
export HOSTCC="$CC"
export BUILD_CC="$CC"
export BUILD_CXX="$CXX"

# ---- helper: download ----
dl() {
  local out="$1"; shift
  # Prefer FuzzBench-provided _dl_retry if present.
  if command -v _dl_retry >/dev/null 2>&1; then
    # Convention: _dl_retry <url1> [url2] [url3] <out>
    _dl_retry "$1" "${2:-}" "${3:-}" "$out"
    return 0
  fi
  # Fallback: curl with retries
  curl -fL --retry 8 --retry-delay 3 --connect-timeout 20 --max-time 600 -o "$out" "$1"
}

# ---- get source ----
WORK="/tmp/binutils_work"
rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"

# Reuse pre-bundled source if present
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

# ---- build (out-of-tree) ----
BUILD_DIR="$WORK/build"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Explicitly pass toolchain variables so configure/make don't accidentally fall back.
# Also propagate common tool vars to reduce surprises.
CC="$CC" CXX="$CXX" \
CFLAGS="$CFLAGS" CXXFLAGS="$CXXFLAGS" \
AR="${AR:-ar}" RANLIB="${RANLIB:-ranlib}" NM="${NM:-nm}" STRIP="${STRIP:-strip}" \
"$SRC_DIR/configure" \
  --disable-shared \
  --disable-gdb \
  --disable-libdecnumber \
  --disable-readline \
  --disable-sim \
  --disable-werror \
  --disable-nls

make -j"$(nproc)" \
  CC="$CC" CXX="$CXX" \
  CFLAGS="$CFLAGS" CXXFLAGS="$CXXFLAGS" \
  AR="${AR:-ar}" RANLIB="${RANLIB:-ranlib}"

# ---- install target binary into OUT ----
mkdir -p "$OUT"
cp -f "$BUILD_DIR/binutils/objdump" "$OUT/objdump"

# ---- sanity check: ensure instrumentation exists (fail fast) ----
# AFL-instrumented binaries typically contain __afl or AFL_ markers.
if command -v strings >/dev/null 2>&1; then
  if ! strings "$OUT/objdump" | grep -Eq "__afl|AFL_"; then
    echo "ERROR: $OUT/objdump appears to be non-instrumented (no AFL markers found)." >&2
    echo "Check that CC/CXX are set to AFL compiler wrappers and that build did not fall back to system gcc/clang." >&2
    echo "CC=$CC CXX=$CXX" >&2
    exit 1
  fi
fi

# ---- seed corpus ----
SEED_DIR="$OUT/seeds"
rm -rf "$SEED_DIR"
mkdir -p "$SEED_DIR"

# Avoid pipefail + head causing SIGPIPE=141 to abort the script
set +o pipefail
find "$BUILD_DIR" -name "*.o" -print | head -n 100 | while read -r f; do
  cp -f "$f" "$SEED_DIR/" || true
done
set -o pipefail

if ls -1 "$SEED_DIR"/* >/dev/null 2>&1; then
  zip -j "$OUT/objdump_seed_corpus.zip" "$SEED_DIR"/* >/dev/null
else
  (cd "$SEED_DIR" && zip -j "$OUT/objdump_seed_corpus.zip" . >/dev/null) || true
fi

rm -rf "$SEED_DIR"