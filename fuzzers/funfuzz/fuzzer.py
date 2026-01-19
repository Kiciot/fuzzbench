from fuzzers import utils
import os

def build():
    """Build benchmark."""
    # 必须与 builder.Dockerfile 中的实际编译路径一致
    # 仓库下的子目录
    fuzzer_root = '/funfuzz_repo/aflpp-fun'
    
    c_compiler = os.path.join(fuzzer_root, 'afl-clang-fast')
    cxx_compiler = os.path.join(fuzzer_root, 'afl-clang-fast++')

    # 设置环境变量
    env = {
        'CC': c_compiler,
        'CXX': cxx_compiler,
        'AFL_LLVM_MODE': '1',  # 启用 LLVM 模式
        'AFL_QUIET': '1',
        # 有些老版本 AFL++ 可能需要这个
        'AFL_PATH': fuzzer_root
    }

    # 调用构建
    utils.build_benchmark(
        fuzzer_name_or_path='funfuzz',
        env=env
    )