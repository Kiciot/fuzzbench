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

# 显式使用 C 编译器 (AFL++ 等会自动设置 CC/CXX)
# binutils 2.26 较老，不仅要关掉 Werror，还要处理一些老旧代码的兼容性
export CFLAGS="$CFLAGS -Wno-error -Wno-deprecated -Wno-unused-variable"
export CXXFLAGS="$CXXFLAGS -Wno-error -Wno-deprecated -Wno-unused-variable"

# 1. 配置
# --disable-shared: 静态链接，方便 Fuzzing
# --disable-gdb: 我们只需要 binutils 工具，不需要 gdb
# --disable-libdecnumber, --disable-readline, --disable-sim: 禁用不必要的组件加速编译
./configure --disable-shared --disable-gdb --disable-libdecnumber --disable-readline --disable-sim --disable-werror

# 2. 编译
make -j$(nproc)

# 3. 复制目标文件
# Binutils 编译好的文件通常在 binutils/ 目录下
# 我们将其重命名为 nm-new 以符合 benchmark 名字
cp binutils/nm-new $OUT/nm-new

# 4. 生成种子
# 我们使用 binutils 源码中的一些对象文件作为种子
mkdir -p $OUT/seeds
find . -name "*.o" | head -n 100 | xargs -I {} cp {} $OUT/seeds/
zip -j $OUT/nm-new_seed_corpus.zip $OUT/seeds/*
rm -rf $OUT/seeds
