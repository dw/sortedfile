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
Efficient seeking within sorted text files. Works by implementing in-place
binary search on the lines of the file, with a small hack to the first line of
the file.

See accompanying README.md for more information.
"""

import itertools
import os


def _getsize(fp):
    """Return the size of `fp` if possible, otherwise raise ValueError."""
    if hasattr(fp, 'getvalue'):
        return len(fp.getvalue())
    elif os.path.exists(fp.name):
        return os.path.getsize(fp.name)
    else:
        raise ValueError("can't get size of %r" % (fp,))


def bisect_seek_left(fp, x, lo=None, hi=None, key=None, _stats=None):
    """Position the sorted seekable file `fp` such that all preceding lines are
    less than `x`. If `x` is present, the file will be positioned on its first
    occurrence."""
    key = key or (lambda s: s)
    # If user specifies the exact start of a line, due to logic below we always
    # skip the first read substring after a seek. Subtract one here to
    # counteract that.
    lo = (lo - 1) if lo else 0
    hi = hi or _getsize(fp)

    count = 0
    while lo < hi:
        mid = (lo + hi) // 2
        fp.seek(mid)
        if mid:
            fp.readline()
        s = fp.readline()
        if s and key(s) < x:
            lo = mid + 1
        else:
            hi = mid
        count += 1

    if _stats:
        _stats[0] = count

    fp.seek(lo)
    if lo:
        fp.readline()


def bisect_seek_right(fp, x, lo=None, hi=None, key=None):
    """Position the sorted seekable file `fp` such that all subsequent lines
    are greater than `x`. If `x` is present, the file will be positioned past
    its last occurrence."""
    key = key or (lambda s: s)
    # If user specifies the exact start of a line, due to logic below we always
    # skip the first read substring after a seek. Subtract one here to
    # counteract that.
    lo = (lo - 1) if lo else 0
    hi = hi or _getsize(fp)

    while lo < hi:
        mid = (lo + hi) // 2
        fp.seek(mid)
        if mid:
            fp.readline()
        s = fp.readline()
        if s and x < key(s):
            hi = mid
        else:
            lo = mid + 1

    fp.seek(lo)
    if lo:
        fp.readline()


def iter_inclusive(fp, x, y, lo=None, hi=None, key=None, _stats=None):
    """Iterate lines of the sorted seekable file `fp` satisfying the condition
    `x <= line <= y`."""
    key = key or (lambda s: s)
    bisect_seek_left(fp, x, lo, hi, key, _stats=_stats)
    pred = lambda s: x <= key(s) <= y
    return itertools.takewhile(pred, fp)


def iter_exclusive(fp, x, y, lo=None, hi=None, key=None):
    """Iterate lines of the sorted seekable file `fp` satisfying the condition
    `x < line < y`."""
    key = key or (lambda s: s)
    bisect_seek_right(fp, x, lo, hi, key)
    pred = lambda s: x < key(s) < y
    return itertools.takewhile(pred, fp)
