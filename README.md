![Don't be like NoSQL Architect](http://i.imgur.com/hNNkn.jpg)

sortedfile
==========

When handling very large text files (for example, Apache logs), it is often
desirable to quickly access some subset without first splitting or import to a
database where a slow index creation process would be required.

When a file is already sorted (in the case of Apache logs, inherently so, since
they're generated in time order), we can exploit this using bisection search to
locate the beginning of the interesting subset.

Due to the nature of bisection this is O(log N) with the limiting factor being
the speed of a disk seek. Given a 1 terabyte file, 40 seeks are required,
resulting in an expected 600ms search time on a rusty old disk drive given
pessimistic constraints.

Things look even better on an SSD where less than 1ms seeks are common, the
same scenario could yield in excess of 25 lookups/second.


Interface
---------

There are 4 main functions. In addition to what is described below, each
function takes the following optional parameters:

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
  UNIX special device, or a file-like object), specifies the highest bound that
  can be seeked.

And now the functions:

``bisect_seek_left(fp, x, lo=None, hi=None, key=None)``:
  Position the sorted seekable file ``fp`` such that all preceding lines are
  less than ``x``. If ``x`` is present, the file will be positioned on its
  first occurrence.

``bisect_seek_right(fp, x, lo=None, hi=None, key=None)``:
  Position the sorted seekable file `fp` such that all subsequent lines are
  greater than ``x``. If ``x`` is present, the file will be positioned past its
  last occurrence.

``iter_inclusive(fp, x, y, lo=None, hi=None, key=None)``:
  Iterate lines of the sorted seekable file ``fp`` satisfying the condition
  ``x <= line <= y``.

``iter_exclusive(fp, x, y, lo=None, hi=None, key=None)``:
  Iterate lines of the sorted seekable file `fp` satisfying the condition
  ``x < line < y``.


Example
-------

    def parse_ts(s):
        """Parse a UNIX syslog format date out of s."""
        time.strptime(' '.join(s.split()[:3]), '%b %d %H:%M:%S')

    fp = file('/var/log/messages')
    # Copy a time range from syslog to stdout.
    it = sortedfile.iter_inclusive(fp,
        x=parse_ts('Nov 20 00:00:00'),
        y=parse_ts('Nov 25 23:59:59'),
        key=parse_ts)
    sys.stdout.writelines(it)


Performance
-----------

Tests using a 100gb file containing 1.07 billion 100 byte records. Immediately
after running ``/usr/bin/purge`` on my 2010 Macbook with a SAMSUNG HN-M500MBB,
we get:

    [21:06:17 Eldil!29 sortedfile] python bigtest.py 
    rec 909916882 len 1 in 193ms
    rec 140582128 len 1 in 126ms
    rec 893294258 len 1 in 125ms
    rec 691277719 len 1 in 135ms
    35 recs in 5.11s (avg 145ms 36 seeks 4ms/seek dist 24352mb / 6.85/sec)

A little while later:

    889 recs in 60.43s (avg 67ms 36 seeks 1ms/seek dist 35514mb / 14.71/sec)

Not bad for spinning rust! ``bigtest.py`` could be tweaked to more thoroughly
dodge the various caches at work, but seems a realistic enough test as-is.
