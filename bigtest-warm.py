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
Like bigtest.py, but use mmap and assume lower 4% of the dataset is hot (42.9
million recs / 4gb).
"""

import os
import mmap
import random
import time

import numpy
import sortedfile

ubound = 1073741823
lbound = int(ubound - (ubound * .04))

# hot = numpy.random.randint(lbound, ubound, size=ubound-lbound)

fp = file('/Users/dmw/big')
hi = sortedfile.getsize(fp)
mem = mmap.mmap(fp.fileno(), hi, mmap.MAP_SHARED, mmap.ACCESS_READ)


t0 = time.time()
mem.seek(lbound * 100)
for i, _ in enumerate(iter(lambda: mem.read(10485760), '')):
    if not i % 100:
        print 'warm %dmb' % (i * 10)

ms = int(1000 * (time.time() - t0))
print 'done cache warm in', ms, 'ms'


start_time = time.time()
count = 0
total_distance = 0
last_stats = time.time()

last = None

rfd, wfd = os.pipe()
rfp = os.fdopen(rfd, 'r', 8)

monitor = bool(os.fork())
if monitor:
    while True:
        count = numpy.fromstring(rfp.read(8), dtype='int32').sum()
        last_stats = time.time()
        print '%d recs in %.2fs (avg %dus dist %dmb / %.2f/sec)' %\
            (count, last_stats - start_time,
             (1000000 * (last_stats - start_time)) / count,
             (100 * (total_distance / count)) / 1048576.,
             1000 / ((1000 * (last_stats - start_time)) / count))

node = 0 if os.fork() else 1

last = numpy.random.randint(lbound, ubound)

while True:
    record = numpy.random.randint(lbound, ubound)
    lst = map(int, sortedfile.iter_inclusive(mem, record, record, hi=hi,
        key=int))
    assert lst == [record]
    total_distance += abs(record - last)
    count += 1
    if (last_stats + 5) < time.time():
        os.write(wfd, numpy.array([count], dtype='int32'))
        last_stats = time.time()
    last = record
