
<div style="text-align: center">
<img title="Don't be like NoSQL Architect" src="http://i.imgur.com/hNNkn.jpg">
</div>


## sortedfile

When handling very large text files (for example, Apache logs), it is often
desirable to quickly access some subset without first splitting or import to a
database where a slow index creation process would be required.

When a file is already sorted (in the case of Apache logs, inherently so, since
they're generated in time order), we can exploit this using bisection search to
locate the beginning of the interesting subset.

Due to the nature of bisection this is O(log N) with the limiting factor being
the speed of a disk seek. Given a 1 terabyte file, 40 seeks are required,
resulting in an *expected* 600ms search time on a rusty old disk drive given
pessimistic constraints. Things look better on an SSD where less than 1ms seeks
are common, the same scenario could yield in excess of 25 lookups/second.


### Interface

There are 6 functions provided for dealing with variable length lines, or
fixed-length records. In addition to what is described below, each function
takes the following optional parameters:

``key``:
  If specified, indicates a function (in the style of ``sorted(..., key=)``)
  that maps each line in the file to an ordered Python object, which will then
  be used for comparison. Provide a key function to extract, for example, the
  unique ID or timestamp from the lines in your files.

  If no key function is given, lines are compared lexicographically.

``lo``:
  Lower search bound in bytes. Use this to skip e.g. undesirable header lines,
  or to constrain a search using a previously successful search. Search will
  actually include one byte prior to this offset, in order to guarantee the
  function has seen a complete line.

``hi``:
  Upper search bound in bytes. If the file being searched is weird (e.g. it's a
  UNIX special device, or a file-like object or ``mmap.mmap``), specifies the
  highest bound that can be seeked.

And now the functions:

``bisect_seek_left(fp, x, lo=None, hi=None, key=None)``:
  Position the sorted seekable file ``fp`` such that all preceding lines are
  less than ``x``. If ``x`` is present, the file is positioned on its first
  occurrence.

``bisect_seek_right(fp, x, lo=None, hi=None, key=None)``:
  Position the sorted seekable file ``fp`` such that all subsequent lines are
  greater than ``x``. If ``x`` is present, the file is positioned past its last
  occurrence.

``bisect_seek_fixed_left(fp, n, x, lo=None, hi=None, key=None)``:
  Position the sorted seekable file ``fp`` such that all preceding ``n`` byte
  records are less than ``x``. If ``x`` is present, the file is positioned on
  its first occurrence.

``bisect_seek_fixed_right(fp, n, x, lo=None, hi=None, key=None)``:
  Position the sorted seekable file ``fp`` such that all subsequent ``n`` byte
  records are greater than ``x``. If ``x`` is present, the file is positioned
  past its last occurrence.

``iter_inclusive(fp, x, y, lo=None, hi=None, key=None)``:
  Iterate lines of the sorted seekable file ``fp`` satisfying the condition
  ``x <= line <= y``.

``iter_exclusive(fp, x, y, lo=None, hi=None, key=None)``:
  Iterate lines of the sorted seekable file `fp` satisfying the condition
  ``x < line < y``.

``iter_fixed_inclusive(fp, n, x, y, lo=None, hi=None, key=None)``:
  Iterate ``n`` byte records of the sorted seekable file ``fp`` satisfying the
  condition ``x <= record <= y``.

``iter_fixed_exclusive(fp, n, x, y, lo=None, hi=None, key=None)``:
  Iterate ``n`` byte records of the sorted seekable file ``fp`` satisfying the
  condition ``x < record < y``.


### Example

    def parse_ts(s):
        """Parse a UNIX syslog format date out of `s`."""
        return time.strptime(' '.join(s.split()[:3]), '%b %d %H:%M:%S')

    fp = file('/var/log/messages')
    # Copy a time range from syslog to stdout.
    it = sortedfile.iter_inclusive(fp,
        x=parse_ts('Nov 20 00:00:00'),
        y=parse_ts('Nov 25 23:59:59'),
        key=parse_ts)
    sys.stdout.writelines(it)


### Cold Performance

Tests using a 100gb file containing 1.07 billion 100 byte records. Immediately
after running ``/usr/bin/purge`` on my 2010 Macbook with a SAMSUNG HN-M500MBB,
we get:

    sortedfile] python bigtest_cold.py 
    46 recs in 5.08s (avg 110ms dist 31214mb / 9.05/sec)

A little while later:

    770 recs in 60.44s (avg 78ms dist 33080mb / 12.74/sec)

And the fixed record variant:

    sortedfile] python bigtest_fixed_cold.py 
    85 recs in 5.01s (avg 58ms dist 33669mb / 16.96/sec)
    172 recs in 10.04s (avg 58ms dist 34344mb / 17.13/sec)
    ...
    1160 recs in 60.28s (avg 51ms dist 35038mb / 19.24/sec)

19 random reads per second on a 1 billion record data set, not bad for spinning
rust! ``bigtest_cold.py`` could be tweaked to more thoroughly dodge the various
caches at work, but seems a realistic enough test as-is.


### Hot Performance

``bigtest_warm.py`` is a more interesting test: instead of uniformly
distributed load over the full set, readers are only interested in recent data.
Without straying too far into kangaroo benchmark territory, it's fair to say
this is a common case.

Requests are randomly generated for the most recent 4% of the file (i.e. 4GB or
43 million records), with an initial warming that pre-caches the range most
reads are serviced by. ``mmap.mmap`` is used in place of ``file`` for its
significant performance benefits when disk IO is fast (i.e. cached).

After warmup it ``fork()``s twice to make use of both cores.

    sortedfile] python bigtest_warm.py 
    warm 0mb
    ...
    warm 4000mb
    done cache warm in 9159 ms
    48979 recs in 5.00s (avg 102us dist 0mb / 9793.93/sec)
    99043 recs in 10.00s (avg 100us dist 0mb / 9902.86/sec)
    ...
    558801 recs in 55.02s (avg 98us dist 0mb / 10156.87/sec)
    611674 recs in 60.00s (avg 98us dist 0mb / 10194.00/sec)

And the fixed variant:

    sortedfile] python bigtest_fixed_warm.py 
    warm 0mb
    ...
    warm 4000mb
    done cache warm in 56333 ms
    57496 recs in 5.01s (avg 87us dist 0mb / 11472.44/sec)
    118194 recs in 10.00s (avg 84us dist 0mb / 11818.55/sec)
    ...
    687029 recs in 55.00s (avg 80us dist 0mb / 12490.89/sec)
    751375 recs in 60.01s (avg 79us dist 0mb / 12521.16/sec)

Around 6250 random reads per second per core on 43 million hot records from a 1
billion record set, all using a plain text file as our "database" and a 23 line
Python function as our engine! Granted it only parses an integer from the
record, however even if the remainder of the record contained, say, JSON, a
single string split operation to remove the key would not overly hurt these
numbers.

There is an unfortunate limit: as ``mmap.mmap`` does not drop the GIL during a
read, page faults are enough to hang a process attempting to serve clients
using multiple threads. ``file`` does not have this problem, nor does forking a
new process per client, or maintaining a process pool.


### A note on buffering

When using ``file``, performance may vary according to the buffer size set for
the file and the target workload. For random reads of single records, a buffer
size that approximates the average record length will work better, whereas for
quick seeks followed by long sequential reads, a larger size is preferable.

Although untested a combination may also work, where one file is used for
searching while another is used for sequential reads (using e.g.
``seq_fp.seek(search_fp.tell())``)
