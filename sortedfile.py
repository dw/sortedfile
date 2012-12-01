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
binary search on the lines of the file, with a small hack to handle the first
line of the file.

See accompanying documentation for more information.
http://sortedfile.readthedocs.org/
"""

# If user specifies the exact start of a line using the `lo` parameter, due to
# logic below we always skip the first read substring after a seek. Therefore
# we subtract one from `lo` if it is provided to the bisect() functions to
# ensure the user's full intended line is seen.

import functools
import itertools
import os

try:
    from mmap import mmap as _mmap
except ImportError:
    _mmap = None


def getsize(fp):
    """Return the size of `fp` if it is a physical file, ``StringIO``, or
    ``mmap.mmap``, otherwise raise ValueError."""
    if hasattr(fp, 'getvalue'):
        return len(fp.getvalue())
    elif _mmap and isinstance(fp, _mmap):
        return len(fp)
    elif hasattr(fp, 'name') and os.path.exists(fp.name):
        return os.path.getsize(fp.name)
    else:
        raise ValueError("can't get size of %r" % (fp,))


def warm(fp, lo=None, hi=None):
    """Encourage the seekable file `fp` to become cached by reading from it
    sequentially."""
    lo = lo or 0
    hi = hi or getsize(fp)
    fp.seek(lo)
    s = ' '
    while s and hi >= 0:
        s = fp.read(10485760)
        hi -= len(s) if s else hi


def bisect_seek_left(fp, x, lo=None, hi=None, key=None):
    """Position the sorted seekable file `fp` such that all preceding lines are
    less than `x`. If `x` is present, the file is positioned on its first
    occurrence."""
    lo = (lo - 1) if lo else 0
    hi = hi or getsize(fp)
    key = key or (lambda s: s)

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

    fp.seek(lo)
    if lo:
        fp.readline()


def bisect_seek_right(fp, x, lo=None, hi=None, key=None):
    """Position the sorted seekable file `fp` such that all subsequent lines
    are greater than `x`. If `x` is present, the file is positioned past its
    last occurrence."""
    lo = (lo - 1) if lo else 0
    hi = hi or getsize(fp)
    key = key or (lambda s: s)

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


def bisect_seek_fixed_left(fp, n, x, lo=None, hi=None, key=None):
    """Position the sorted seekable file `fp` such that all preceding `n` byte
    records are less than `x`. If `x` is present, the file is positioned on its
    first occurrence."""
    lo = lo or 0
    key = key or (lambda s: s)
    rlo = lo / n
    rhi = (hi or getsize(fp)) / n

    while rlo < rhi:
        mid = (rlo + rhi) // 2
        fp.seek(lo + (mid * n))
        s = fp.read(n)
        if s and key(s) < x:
            rlo = mid + 1
        else:
            rhi = mid

    fp.seek(lo + (rlo * n))


def bisect_seek_fixed_right(fp, n, x, lo=None, hi=None, key=None):
    """Position the sorted seekable file `fp` such that all subsequent `n` byte
    records are greater than `x`. If `x` is present, the file is positioned
    past its last occurrence."""
    lo = lo or 0
    key = key or (lambda s: s)
    rlo = lo / n
    rhi = (hi or getsize(fp)) / n

    while rlo < rhi:
        mid = (rlo + rhi) // 2
        fp.seek(lo + (mid * n))
        s = fp.read(n)
        if s and x < key(s):
            rhi = mid
        else:
            rlo = mid + 1

    fp.seek(lo + (rlo * n))


def bisect_func_left(x, lo, hi, func):
    """Bisect `func(i)`, returning an index such that preceding values are less
    than `x`. If `x` is present, the returned index is its first occurrence.
    EOF is assumed if `func` returns None."""
    while lo < hi:
        mid = (lo + hi) // 2
        k = func(mid)
        if k is not None and k < x:
            lo = mid + 1
        else:
            hi = mid

    return lo


def bisect_func_right(x, lo, hi, func):
    """Bisect `func(i)`, returning an index such that consecutive values are
    greater than `x`. If `x` is present, the returned index is past its last
    occurrence. EOF is assumed if `func` returns None."""
    while lo < hi:
        mid = (lo + hi) // 2
        k = key_at(mid)
        if k is not None and x < k:
            hi = mid
        else:
            lo = mid + 1

    return lo


def extents(fp, lo=None, hi=None):
    """Return a tuple of the first and last lines from the seekable file
    `fp`."""
    lo = (lo - 1) if lo else 0
    hi = hi or getsize(fp)
    bisect_seek_left(fp, '', lo, hi)
    low = fp.readline()

    for offset in xrange(0, 1048576, 4096):
        fp.seek(hi - offset)
        _, sep, high = fp.read(offset - 1).rstrip('\n').rpartition('\n')
        if sep:
            return low, high


def extents_fixed(fp, n, lo=None, hi=None):
    """Return a tuple of the first and last `n` byte records from the seekable
    file `fp`."""
    lo = lo or 0
    hi = hi or getsize(fp)
    bisect_seek_fixed_left(fp, n, '', lo, hi)
    low = fp.read(n)
    recs = (hi - lo) // n
    fp.seek(lo + (n * (recs - 1)))
    return low, fp.read(n)


def iter_inclusive(fp, x, y, lo=None, hi=None, key=None):
    """Iterate lines of the sorted seekable file `fp` satisfying
    `x <= line <= y`."""
    key = key or (lambda s: s)
    bisect_seek_left(fp, x, lo, hi, key)
    pred = lambda s: x <= key(s) <= y
    return itertools.takewhile(pred, iter(fp.readline, ''))


def iter_exclusive(fp, x, y, lo=None, hi=None, key=None):
    """Iterate lines of the sorted seekable file `fp` satisfying
    `x < line < y`."""
    key = key or (lambda s: s)
    bisect_seek_right(fp, x, lo, hi, key)
    pred = lambda s: x < key(s) < y
    return itertools.takewhile(pred, iter(fp.readline, ''))


def iter_fixed_inclusive(fp, n, x, y, lo=None, hi=None, key=None):
    """Iterate `n` byte records of the sorted seekable file `fp` satisfying
    `x <= record <= y`."""
    key = key or (lambda s: s)
    bisect_seek_fixed_left(fp, n, x, lo, hi, key)
    pred = lambda s: x <= key(s) <= y
    return itertools.takewhile(pred, iter(functools.partial(fp.read, n), ''))


def iter_fixed_exclusive(fp, n, x, y, lo=None, hi=None, key=None):
    """Iterate `n` byte records of the sorted seekable file `fp` satisfying
    `x < record < y`."""
    key = key or (lambda s: s)
    bisect_seek_fixed_right(fp, n, x, lo, hi, key)
    pred = lambda s: x < key(s) < y
    return itertools.takewhile(pred, iter(functools.partial(fp.read, n), ''))
