#!/bin/bash
set -e

# 针对旧版代码的编译器兼容性修正
# -Wno-error: 防止将警告视为错误（旧代码警告很多）
# -static: 静态链接
export CFLAGS="$CFLAGS -Wno-error"
export CXXFLAGS="$CXXFLAGS -Wno-error"

# 1. 配置
# --disable-werror 对于老版本至关重要
./configure \
    --disable-shared \
    --disable-gdb \
    --disable-libdecnumber \
    --disable-readline \
    --disable-sim \
    --disable-werror

# 2. 编译
make -j$(nproc)

# 3. 复制目标程序
# 2.28 版本的 readelf 编译后应该在 binutils/ 目录下
cp binutils/readelf $OUT/readelf-fuzz

# 4. 准备种子 (Seeds)
# 直接用刚编译出的二进制文件作为种子
mkdir -p $OUT/seeds
cp binutils/readelf $OUT/seeds/seed_elf_binary_1
# 也可以找个 .o 文件
find . -name "*.o" | head -n 5 | xargs -I {} cp {} $OUT/seeds/

# 5. 准备字典 (Dictionary)
# 手动写入一个针对 ELF 的最小字典
cat > $OUT/readelf.dict <<EOF
"ELF"
"\x7fELF"
"\x01\x01\x01"
".text"
".data"
".bss"
".rodata"
".symtab"
".strtab"
".shstrtab"
EOF