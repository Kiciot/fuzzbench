# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration code for libFuzzer entropic mode."""

import os
import subprocess

from fuzzers import utils


def build():
    """Build benchmark with libFuzzer (no-link) and custom libFuzzer.a."""
    cflags = ['-fsanitize=fuzzer-no-link']
    utils.append_flags('CFLAGS', cflags)
    utils.append_flags('CXXFLAGS', cflags)

    os.environ['CC'] = 'clang'
    os.environ['CXX'] = 'clang++'
    os.environ['FUZZER_LIB'] = '/usr/lib/libFuzzer.a'

    utils.build_benchmark()


def fuzz(input_corpus, output_corpus, target_binary):
    """Run fuzzer with entropic scheduling enabled."""
    run_fuzzer(input_corpus, output_corpus, target_binary)


def run_fuzzer(input_corpus, output_corpus, target_binary, extra_flags=None):
    """Run libFuzzer in entropic mode."""
    if extra_flags is None:
        extra_flags = []

    crashes_dir = os.path.join(output_corpus, 'crashes')
    corpus_dir = os.path.join(output_corpus, 'corpus')
    os.makedirs(crashes_dir, exist_ok=True)
    os.makedirs(corpus_dir, exist_ok=True)

    # Enable symbolization if focus_function is used.
    for flag in extra_flags:
        if flag.startswith('-focus_function'):
            if os.environ.get('ASAN_OPTIONS'):
                os.environ['ASAN_OPTIONS'] += ':symbolize=1'
            else:
                os.environ['ASAN_OPTIONS'] = 'symbolize=1'

            if os.environ.get('UBSAN_OPTIONS'):
                os.environ['UBSAN_OPTIONS'] += ':symbolize=1'
            else:
                os.environ['UBSAN_OPTIONS'] = 'symbolize=1'
            break

    flags = [
        '-print_final_stats=1',
        '-close_fd_mask=3',
        '-fork=1',
        '-ignore_ooms=1',
        '-ignore_timeouts=1',
        '-ignore_crashes=1',
        '-detect_leaks=0',
        f'-artifact_prefix={crashes_dir}/',

        # Entropic mode
        '-entropic=1',
        '-keep_seed=1',
        '-cross_over_uniform_dist=1',
        '-entropic_scale_per_exec_time=1',
    ]

    flags += extra_flags

    if os.environ.get('ADDITIONAL_ARGS'):
        flags += os.environ['ADDITIONAL_ARGS'].split()

    dictionary_path = utils.get_dictionary_path(target_binary)
    if dictionary_path:
        flags.append('-dict=' + dictionary_path)

    command = [target_binary] + flags + [corpus_dir, input_corpus]
    print('[run_fuzzer] Running command: ' + ' '.join(command))
    subprocess.check_call(command)