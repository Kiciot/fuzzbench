#!/bin/bash -eu
################################################################################
# Copyright 2018 Google Inc.
# Licensed under the Apache License, Version 2.0
################################################################################

mkdir -p build
cd build
cmake -DCMAKE_CXX_COMPILER="$CXX" -DCMAKE_CXX_FLAGS="$CXXFLAGS" \
      -DJSONCPP_WITH_POST_BUILD_UNITTEST=OFF -DJSONCPP_WITH_TESTS=OFF \
      -DBUILD_SHARED_LIBS=OFF -G "Unix Makefiles" ..
make -j"$(nproc)"

# Compile fuzzer.
$CXX $CXXFLAGS -I../include \
    ../src/test_lib_json/fuzz.cpp -o "$OUT/jsoncpp_fuzzer" \
    lib/libjsoncpp.a $LIB_FUZZING_ENGINE

# Dictionary
cp "$SRC/jsoncpp/src/test_lib_json/fuzz.dict" "$OUT/jsoncpp_fuzzer.dict"

# ---------------- seed corpus ----------------
SEED_DIR="$SRC/jsoncpp_seed"
rm -rf "$SEED_DIR"
mkdir -p "$SEED_DIR"

# Minimal valid JSON samples (must be non-empty corpus)
cat > "$SEED_DIR/empty_object.json" <<'EOF'
{}
EOF
cat > "$SEED_DIR/empty_array.json" <<'EOF'
[]
EOF
cat > "$SEED_DIR/simple.json" <<'EOF'
{"a":1,"b":[true,false,null],"c":"x"}
EOF

zip -j "$OUT/jsoncpp_fuzzer_seed_corpus.zip" "$SEED_DIR"/* >/dev/null