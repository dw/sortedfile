
sortedfile
==========

`http://github.com/dw/sortedfile <http://github.com/dw/sortedfile>`_

.. toctree::
    :hidden:
    :maxdepth: 2


When handling large text files it is often desirable to access some subset
without first splitting, or importing to a database where an index creation
process is required. When data is already sorted (inherently in the case of
logs or time series data, as they're generated in time order), we can exploit
this property using binary search to efficiently locate interesting subsets.

Due to the nature of binary search this is O(log N) with the limiting factor
being the speed of a disk seek. Given a 1 terabyte file, 40 seeks are required,
resulting in an *expected* 600ms search time on a rusty old disk given
pessimistic assumptions. Things look better on an SSD where less than 1ms seeks
are common: the same scenario could yield in excess of 25 lookups/second.


Common Parameters
#################

In addition to those described later, each function accepts the following
optional parameters:

``key``:
  Indicates a function (in the style of ``sorted(..., key=)``) that maps lines
  to ordered values to be used for comparison. Provide ``key`` to extract a
  unique ID or timestamp. Lines are compared lexicographically by default.

``lo``:
  Lowest offset in bytes, useful for skipping headers or to constrain a search
  using a previous search. For line oriented search, one byte prior to this
  offset is included in order to ensure the first line is considered complete.
  Defaults to ``0``.

``hi``:
  Highest offset in bytes. If the file being searched is weird (e.g. a UNIX
  special device), specifies the highest bound to access. By default
  ``getsize()`` is used to probe the file size.


Interface
#########

Five functions are provided in two variants, one for variable length lines and
one for fixed-length records. Fixed length versions are more efficient as they
require ``log(length)`` fewer steps than bytewise search.

For line oriented functions, a `seekable file` is any object with functional
``readline()`` and ``seek()``, whereas for record oriented functions it is any
object with ``read()`` and ``seek()``.


Search Functions
++++++++++++++++

.. autofunction:: sortedfile.bisect_seek_left
.. autofunction:: sortedfile.bisect_seek_right
.. autofunction:: sortedfile.bisect_seek_fixed_left
.. autofunction:: sortedfile.bisect_seek_fixed_right


Iteration Functions
+++++++++++++++++++

.. autofunction:: sortedfile.iter_exclusive
.. autofunction:: sortedfile.iter_inclusive
.. autofunction:: sortedfile.iter_fixed_exclusive
.. autofunction:: sortedfile.iter_fixed_inclusive


Utility Functions
+++++++++++++++++

.. autofunction:: sortedfile.extents
.. autofunction:: sortedfile.extents_fixed
.. autofunction:: sortedfile.getsize
.. autofunction:: sortedfile.warm


Example
#######

::

    def parse_ts(s):
        """Parse a UNIX syslog format date out of `s`."""
        return time.strptime(s[:15], '%b %d %H:%M:%S')

    # Copy a time range from syslog to stdout.
    it = sortedfile.iter_inclusive(
        fp=open('/var/log/messages'),
        x=parse_ts('Nov 20 00:00:00'),
        y=parse_ts('Nov 25 23:59:59'),
        key=parse_ts)
    sys.stdout.writelines(it)


Performance
###########

Tests use a 100GB file containing 1.073 billion 100 byte records with the
record number left justified to 99 bytes followed by a newline, allowing both
line and record oriented search.


Cold Cache
++++++++++

After running `/usr/bin/purge <http://developer.apple.com/library/mac/#documentation/Darwin/Reference/ManPages/man8/purge.8.html>`_
on a 2010 Macbook Pro with a $50 Samsung HN-M500MBB:

::

    $ ./bench.py 
    770 recs in 60.44s (avg 78ms dist 33080mb / 12.74/sec)

And the fixed record variant:

::

    $ ./bench.py fixed
    1160 recs in 60.28s (avg 51ms dist 35038mb / 19.24/sec)

19 random searches per second on a billion records, not bad for budget spinning
rust. ``bench.py`` could be tweaked to more thoroughly dodge the various
caches in play, but seems a fair test as-is.

Reading 100 consecutive records following each search provides some indication
of throughput in a common case:

::

    $ ./bench.py fixed span100
    101303 recs in 60.40s (avg 0.596ms / 1677.13/sec)


Hot Cache
+++++++++

``bench.py warm`` is more interesting: instead of load uniformly distributed
over the set, readers only care about recent data. Requests are generated for
the bottom 4% of the file (i.e. 4GB or 43 million records), with an initial
warming that pre-caches this region. ``mmap.mmap`` is used in place of ``file``
for its significant performance edge when IO is fast (e.g. cached).

After warmup, ``fork()`` to avail of both cores:

::

    $ ./bench.py warm mmap smp
    611674 recs in 60.00s (avg 98us dist 0mb / 10194.00/sec)

And the fixed variant:

::

    $ ./bench.py fixed warm mmap smp
    751375 recs in 60.01s (avg 79us dist 0mb / 12521.16/sec)

Around 6250 random reads per second per core over 43 million records from a set
of 1 billion, using only plain sorted text and a 23 line function. Granted it
only parses integers, however even if the remainder contained say, JSON, a
single ``str.partition()`` would not hurt. Processing cost for the returned
data may also vastly outweigh lookup cost.

And for consecutive sequential reads:

::

    $ ./bench.py fixed mmap smp warm span100
    15396036 recs in 60.01s (avg 0.004ms / 256578.04/sec)


Notes
#####


Threads and ``mmap.mmap``
+++++++++++++++++++++++++

Since ``mmap.mmap`` does not drop the GIL during reads, page faults will hang a
process attempting to serve cold data to clients using threads. ``file`` does
not have this problem, nor does forking a process per client, or maintaining a
process pool.


Buffering
+++++++++

When using ``file``, performance may vary according to the buffer size set for
the file and target workload. For random reads of single records, a buffer that
approximates double the average record length will work better, whereas for
searches followed by sequential reads a larger buffer may be preferable.


Interesting Uses
++++++++++++++++

Since the ``bisect`` functions re-check the input file's size on each call when
``hi`` isn't specified, it is trivial to have concurrent readers and writers,
so long as writers take care to open the file as ``O_APPEND``, and emit records
no larger than the maximum atomic write size for the operating system. On
Linux, since ``write()`` holds a lock, it should be possible to write records
of arbitrary size.

However since each region's midpoint will change as the file grows, this mode
may not interact well with OS caching without further mitigation. Another
caveat is that under IO/scheduling contention, it is possible for writes from
multiple processes to occur out of order, although depending on the granularity
of the key this may not be a problem.


Future Improvements
+++++++++++++++++++

It should be possible to squeeze better performance out of ``file`` by paying
attention to the operating system's needs, in particular with regard to read
alignment and the use of ``posix_fadvise``. Single-threaded ``file``
performance is significantly worse than ``mmap.mmap``, this is almost certainly
not inherent, more likely it is due to a badly designed test.

Additionally unlike ``mmap.mmap``, calling ``file.seek()`` invokes a real
system call, which may be generating more work than is apparent. The
implementation could be improved to remove at least some of these calls.
