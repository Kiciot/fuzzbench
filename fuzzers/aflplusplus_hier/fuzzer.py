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
"""Integration code for aflplusplus-hier fuzzer."""

import os

from fuzzers.aflplusplus import fuzzer as aflplusplus_fuzzer


def build(*args):
    """Build benchmark using the AFL++ integration."""
    aflplusplus_fuzzer.build(*args)


def fuzz(input_corpus,
         output_corpus,
         target_binary,
         flags=tuple(),
         skip=False,
         no_cmplog=False):
    """Run aflplusplus-hier using the AFL++ integration."""
    os.environ['AFL_USE_MULTI_LEVEL_COV'] = '1'
    os.environ['AFL_USE_HIER_SCHEDULE'] = '1'

    extra_flags = list(flags)

    if '-d' not in extra_flags:
        extra_flags.append('-d')

    if '-p' not in extra_flags:
        extra_flags.extend(['-p', 'explore'])

    aflplusplus_fuzzer.fuzz(input_corpus,
                            output_corpus,
                            target_binary,
                            flags=tuple(extra_flags),
                            skip=skip,
                            no_cmplog=no_cmplog)