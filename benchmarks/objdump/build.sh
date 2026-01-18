#!/bin/bash -eu
# Copyright 2019 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
################################################################################

# 显式使用编译器配置
export CFLAGS="$CFLAGS -Wno-error -Wno-deprecated -Wno-unused-variable"
export CXXFLAGS="$CXXFLAGS -Wno-error -Wno-deprecated -Wno-unused-variable"

# 1. 配置 (针对 objdump)
./configure --disable-shared --disable-gdb --disable-libdecnumber --disable-readline --disable-sim --disable-werror

# 2. 编译
make -j$(nproc)

# 3. 复制目标文件
# Binutils 编译好的 objdump 通常在 binutils/ 目录下
cp binutils/objdump $OUT/objdump

# 4. 生成种子
# 使用 .o 文件作为种子
mkdir -p $OUT/seeds
find . -name "*.o" | head -n 100 | xargs -I {} cp {} $OUT/seeds/
zip -j $OUT/objdump_seed_corpus.zip $OUT/seeds/*
rm -rf $OUT/seeds
