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

# 显式编译器配置 (Binutils 2.26 需要宽松的检查)
export CFLAGS="$CFLAGS -Wno-error -Wno-deprecated -Wno-unused-variable"
export CXXFLAGS="$CXXFLAGS -Wno-error -Wno-deprecated -Wno-unused-variable"

# 1. 配置
./configure --disable-shared --disable-gdb --disable-libdecnumber --disable-readline --disable-sim --disable-werror

# 2. 编译
make -j$(nproc)

# 3. 复制目标文件
# cxxfilt 编译后通常在 binutils/ 目录下
cp binutils/cxxfilt $OUT/cxxfilt

# 4. 生成种子
# cxxfilt 是做 C++ 符号还原的，我们用一些混淆后的符号作为种子
mkdir -p $OUT/seeds
echo "_Z1fv" > $OUT/seeds/seed1
echo "_Z1fi" > $OUT/seeds/seed2
echo "_Z3fooIiEvT_" > $OUT/seeds/seed3
zip -j $OUT/cxxfilt_seed_corpus.zip $OUT/seeds/*
rm -rf $OUT/seeds
