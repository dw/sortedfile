#!/usr/bin/env python
#
# Copyright 2012, David Wilson
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#    http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
Requires generation of a test file via bigtest_mkbig.py before running.
"""

import functools
import random
import sys
import time

import sortedfile
from bigtest_mkbig import *


fp = file(filename, 'r', reclen)

start_time = time.time()
count = 0
total_distance = 0
total_seeks = 0
last_stats = time.time()

last = None

if 'fixed' in sys.argv:
    print 'using fixed'
    do_iter = functools.partial(sortedfile.iter_fixed_inclusive,
        fp, reclen, key=int)
else:
    do_iter = functools.partial(sortedfile.iter_inclusive,
        fp, key=int)

while True:
    record = random.randint(0, ubound)
    t0  = time.time()
    lst = map(int, do_iter(record, record))
    t1 = time.time()
    if last is None:
        dist = 0
    else:
        dist = abs(record - last)
        total_distance += dist
    if 0 and not (count % 50):
        print 'rec %d len %d in %dms' % (record, len(lst), 1000*(t1-t0))
    count += 1
    assert lst == [record]
    if (last_stats + 5) < time.time():
        last_stats = time.time()
        print '%d recs in %.2fs (avg %dms dist %dmb / %.2f/sec)' %\
            (count, last_stats - start_time,
             (1000 * (last_stats - start_time)) / count,
             (100 * (total_distance / count)) / 1048576.,
             1000 / ((1000 * (last_stats - start_time)) / count))
    last = record
