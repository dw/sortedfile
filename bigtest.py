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

import functools
import mmap
import os
import random
import struct
import sys
import time

import sortedfile


mb = 1048576
filename = '_big.dat'
filesize = mb * 1024 * 100
reclen = 100
ubound = (filesize / reclen) - 1
lbound = 0


if 'make' in sys.argv:
    if os.path.exists(filename):
        print 'Delete old', filename, 'first'
        sys.exit(1)
    with open(filename, 'w', 10 * mb) as fp:
        for i in xrange(filesize / reclen):
            fp.write('%-*d\n' % (reclen - 1, i))
    sys.exit(1)


fp = file(filename, 'r', reclen)
hi = sortedfile.getsize(fp)

if 'mmap' in sys.argv:
    print 'using mmap'
    dfp = mmap.mmap(fp.fileno(), hi, mmap.MAP_SHARED, mmap.ACCESS_READ)
else:
    dfp = fp

if 'fixed' in sys.argv:
    print 'using fixed'
    do_iter = functools.partial(sortedfile.iter_fixed_inclusive,
        dfp, reclen, hi=hi, key=int)
else:
    do_iter = functools.partial(sortedfile.iter_inclusive,
        dfp, hi=hi, key=int)

if 'warm' in sys.argv:
    lbound = int(ubound - (ubound * .04))
    t0 = time.time()
    print 'warm...'
    sortedfile.warm(dfp, lbound * reclen)
    print 'done cache warm in %dms' % (1000 * (time.time() - t0))

if 'span100' in sys.argv:
    span = 100
elif 'span1000' in sys.argv:
    span = 1000
else:
    span = 0

start_time = time.time()
count = 0
total_distance = 0
last_stats = time.time()

nodes = 2 if 'smp' in sys.argv else 1
rfd, wfd = os.pipe()
rfp = os.fdopen(rfd, 'r', 8)

monitor = bool(os.fork())
while monitor:
    count = sum(struct.unpack('=' + ('L'*nodes), rfp.read(4 * nodes)))
    last_stats = time.time()
    print '%d recs in %.2fs (avg %.3fms / %.2f/sec)' %\
        (count, last_stats - start_time,
         (1000 * (last_stats - start_time)) / count,
         1000 / ((1000 * (last_stats - start_time)) / count))

for _ in range(nodes - 1):
    os.fork()

while True:
    record = random.randint(lbound, ubound)
    lst = map(int, do_iter(record, record+span))
    count += len(lst)
    expect = range(record, min(ubound, record+span) + 1)
    assert lst == expect, repr((lst, record))
    if (last_stats + 5) < time.time():
        os.write(wfd, struct.pack('=L', count))
        last_stats = time.time()
    last = record
