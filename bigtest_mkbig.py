
mb = 1048576
filename = '_big.dat'
filesize = mb * 1024 * 100
reclen = 100
ubound = (filesize / reclen) - 1

if __name__ == '__main__':
    with open(filename, 'w', 10 * mb) as fp:
        for i in xrange(filesize / reclen):
            fp.write('%-*d\n' % (reclen - 1, i))

