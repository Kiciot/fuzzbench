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
#
"""Integration code for BeliefFuzz fuzzer."""

import os

from fuzzers.afl import fuzzer as afl_fuzzer
from fuzzers import utils


def get_edge_potential_path(build_directory):
    """Return path to BeliefFuzz edge potential file."""
    return os.path.join(build_directory, 'edge_potential.txt')


def build():
    """Build benchmark using BeliefFuzz's AFL-based compiler flow."""
    build_directory = os.environ['OUT']
    edge_potential_path = get_edge_potential_path(build_directory)

    # BeliefFuzz requires the compiler wrapper to emit edge information with
    # -res=<path>.
    utils.append_flags('CFLAGS', [f'-res={edge_potential_path}'])
    utils.append_flags('CXXFLAGS', [f'-res={edge_potential_path}'])

    afl_fuzzer.build()


def fuzz(input_corpus, output_corpus, target_binary):
    """Run BeliefFuzz with MCTS seed scheduling and regret-based power."""
    afl_fuzzer.prepare_fuzz_environment(input_corpus)

    target_binary_directory = os.path.dirname(target_binary)
    edge_potential_path = get_edge_potential_path(target_binary_directory)

    additional_flags = [
        '-r',
        '-p',
        '-c',
        edge_potential_path,
    ]

    afl_fuzzer.run_afl_fuzz(input_corpus,
                            output_corpus,
                            target_binary,
                            additional_flags=additional_flags)