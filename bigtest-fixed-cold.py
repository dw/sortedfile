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
Requires generation of a 100gb test file before running:

    f = file('/Users/dmw/big', 'w', 10 * 1048576)
    for i in xrange(1073741824):
        f.write('%-99d\n' % i)
"""

import random
import time

import sortedfile

ubound = 1073741823
pick = lambda: random.randint(0, ubound)


fp = file('/Users/dmw/big')

start_time = time.time()
count = 0
total_distance = 0
total_seeks = 0
last_stats = time.time()

last = None

while True:
    record = pick()
    t0  = time.time()
    lst = map(int, sortedfile.iter_fixed_inclusive(fp, 100, record, record,
        key=int))
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
