#!/bin/bash -eu
################################################################################
# Copyright 2018 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

cd libpcap

mkdir -p build
cd build
cmake -DDISABLE_DBUS=1 ..
make -j"$(nproc)"

# build fuzz target
$CC $CFLAGS -I.. -c ../testprogs/fuzz/fuzz_both.c -o fuzz_both.o
$CXX $CXXFLAGS fuzz_both.o -o "$OUT/fuzz_both" libpcap.a $LIB_FUZZING_ENGINE

# options files
cd ..
cp testprogs/fuzz/fuzz_*.options "$OUT/" || true

# ---------------- seed corpus ----------------
SEED_ROOT="$SRC/libpcap_seed"
rm -rf "$SEED_ROOT"
mkdir -p "$SEED_ROOT"

# 1) tcpdump tests (pcap-ish inputs)
if [ -d "$SRC/tcpdump/tests" ]; then
  # copy a subset to avoid huge zips
  find "$SRC/tcpdump/tests" -type f -maxdepth 2 | head -n 200 | while read -r f; do
    cp -f "$f" "$SEED_ROOT/" || true
  done
fi

# 2) BPF corpus (text inputs)
BPF_DIR="$SRC/libpcap/testprogs/BPF"
if [ -d "$BPF_DIR" ]; then
  tmp="$SEED_ROOT/bpf"
  mkdir -p "$tmp"
  (cd "$BPF_DIR" && ls *.txt 2>/dev/null || true) | while read -r i; do
    [ -n "$i" ] || continue
    tail -1 "$BPF_DIR/$i" > "$tmp/$i" || true
  done
  # flatten
  find "$tmp" -type f -maxdepth 1 -exec cp -f {} "$SEED_ROOT/" \; || true
  rm -rf "$tmp"
fi

# Ensure non-empty corpus
if ! ls -1 "$SEED_ROOT"/* >/dev/null 2>&1; then
  echo "ERROR: seed corpus is empty for fuzz_both" >&2
  exit 1
fi

zip -j "$OUT/fuzz_both_seed_corpus.zip" "$SEED_ROOT"/* >/dev/null