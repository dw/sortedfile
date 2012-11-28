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

from __future__ import absolute_import

import cStringIO as StringIO
import time
import unittest

import sortedfile


ZU2 = '''
09/30/2002,0305,3798.0,3798.0,3787.5,3787.5,23,34
09/30/2002,0306,3787.5,3794.0,3785.5,3791.5,38,14
09/30/2002,0326,3812.5,3813.5,3806.0,3808.0,19,27
09/30/2002,0327,3807.0,3808.0,3800.0,3800.0,30,42
09/30/2002,0328,3800.5,3802.5,3795.0,3798.0,61,47
09/30/2002,0329,3798.0,3804.5,3798.0,3804.0,30,21
09/30/2002,0330,3804.0,3804.0,3795.5,3795.5,6,31
09/30/2002,0331,3795.5,3801.5,3794.5,3798.0,20,34
09/30/2002,0332,3798.0,3800.0,3793.5,3797.5,16,17
09/30/2002,0333,3798.0,3801.5,3796.0,3796.5,19,21
09/30/2002,0334,3798.5,3798.5,3794.5,3795.5,5,29
'''.lstrip()


class Zu2TestCase(unittest.TestCase):
    def test_zu2(self):
        def parse_time(s):
            return time.strptime(s, '%m/%d/%Y %H%M')

        def key_func(s):
            time_s = ' '.join(s.split(',', 3)[:2])
            return parse_time(time_s)

        io = StringIO.StringIO(ZU2)
        sortedfile.bisect_seek_left(io, parse_time('10/01/2004 0952'),
            key=key_func)
        self.assertEqual([], list(io))

        it = sortedfile.iter_inclusive(io,
            x=parse_time('09/30/2002 0328'),
            y=parse_time('09/30/2002 0332'),
            key=key_func)
        self.assertEqual(5, len(list(it)))


class BisectTestCase(unittest.TestCase):
    def make_fp(self):
        io = StringIO.StringIO()
        for i in xrange(1, 10):
            for j in xrange(10):
                io.write('%s\n' % i)
        return io

    def test_bisect_left(self):
        io = self.make_fp()
        def test(n, x):
            sortedfile.bisect_seek_left(io, x, key=int)
            self.assertEqual(n, io.tell())

        test(0, 0)
        test(0, 1)
        test(20, 2)
        test(40, 2.5)
        test(40, 3)
        test(len(io.getvalue()), 11)

        io = StringIO.StringIO('')
        test(0, 0)

    def test_bisect_right(self):
        io = self.make_fp()
        def test(n, x):
            sortedfile.bisect_seek_right(io, x, key=int)
            self.assertEqual(n, io.tell())

        test(0, 0)
        test(20, 1)
        test(40, 2)
        test(40, 2.5)
        test(60, 3)
        test(len(io.getvalue()), 11)
        io = StringIO.StringIO('')
        test(0, 0)

    def test_extents(self):
        io = self.make_fp()
        low, high = sortedfile.extents(io)
        self.assertEqual(1, int(low))
        self.assertEqual(9, int(high))

    def test_iter_inclusive(self):
        io = self.make_fp()
        self.assertEqual([1]*10 + [2]*10, map(int,
            sortedfile.iter_inclusive(io, 1, 2, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_inclusive(io, 99, 100, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_inclusive(io, 0, 0.5, key=int)))

    def test_iter_exclusive(self):
        io = self.make_fp()
        self.assertEqual([2]*10, map(int,
            sortedfile.iter_exclusive(io, 1, 3, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_inclusive(io, 99, 100, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_inclusive(io, 0, 0.5, key=int)))


class BisectFixedTestCase(unittest.TestCase):
    def make_fp(self):
        io = StringIO.StringIO()
        for i in xrange(1, 10):
            for j in xrange(10):
                io.write('%-99d\n' % i)
        return io

    def test_bisect_left(self):
        io = self.make_fp()
        def test(n, x):
            sortedfile.bisect_seek_fixed_left(io, 100, x, key=int)
            self.assertEqual(n, io.tell())

        test(0, 0)
        test(0, 1)
        test(1000, 2)
        test(2000, 2.5)
        test(2000, 3)
        test(len(io.getvalue()), 11)

        io = StringIO.StringIO('')
        test(0, 0)

    def test_bisect_right(self):
        io = self.make_fp()
        def test(n, x):
            sortedfile.bisect_seek_fixed_right(io, 100, x, key=int)
            self.assertEqual(n, io.tell())

        test(0, 0)
        test(1000, 1)
        test(2000, 2)
        test(2000, 2.5)
        test(3000, 3)
        test(len(io.getvalue()), 11)
        io = StringIO.StringIO('')
        test(0, 0)

    def test_extents_fixed(self):
        io = self.make_fp()
        low, high = sortedfile.extents_fixed(io, 100)
        self.assertEqual(1, int(low))
        self.assertEqual(9, int(high))

    def test_iter_inclusive(self):
        io = self.make_fp()
        self.assertEqual([1]*10 + [2]*10, map(int,
            sortedfile.iter_fixed_inclusive(io, 100, 1, 2, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_fixed_inclusive(io, 100, 99, 100, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_fixed_inclusive(io, 100, 0, 0.5, key=int)))

    def test_iter_exclusive(self):
        io = self.make_fp()
        self.assertEqual([2]*10, map(int,
            sortedfile.iter_fixed_exclusive(io, 100, 1, 3, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_fixed_inclusive(io, 100, 99, 100, key=int)))
        self.assertEqual([],
            list(sortedfile.iter_fixed_inclusive(io, 100, 0, 0.5, key=int)))


if __name__ == '__main__':
    unittest.main()
