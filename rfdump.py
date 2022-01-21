#!/usr/bin/env python3

from sys import argv, stdout, exit, stderr
from getopt import getopt, GetoptError
from time import time


device_path = '/dev/rfctl'  # for <device> command-line option
dump_time = -1  # for -t command-line option
verbose = 0  # verbose level for -v & -V command-line options
verbose_file, bin_file = None, stdout  # file descriptors for verbose messages & out binary file

usage = f'''
Dumps from device file by 4 bytes LIRC sequence.

Usage: python3 {argv[0]} -v -t <seconds> <device>
	-v          verbose, dump hex values by 4 bytes
	-V          as -v but dump to both: stdout (binary) & stderr (hex)
	<seconds>   dump time; default: forever; example: -t 0.5
	<device>    path to device; default: {device_path}

Examples:
	{argv[0]} > rfdump.bin
	{argv[0]} -V -t .1 > rfdump.bin
'''


def main():
	start_time = time()  # used for dump time
	if verbose_file:
		print(f'Open device file {device_path}', file=verbose_file)
	fd = open(device_path, 'rb')
	fd_read = fd.read
	if verbose_file:
		print(f'Read from device {"for "+str(dump_time)+" seconds" if dump_time > 0 else "forever"}', file=verbose_file)
	try:
		while(True):
			data = fd_read(4)
			if len(data) == 4:
				if verbose_file:
					print(data.hex(), file=verbose_file)
				if bin_file:
					bin_file.buffer.raw.write(data)
			if dump_time > 0 and time() - start_time >= dump_time:
				# dump time is over # stop dump
				fd.close()
				return
	except BrokenPipeError:
		exit(-1)


# process command-line

try:
	optlist, args = getopt(argv[1:], 'hHvVt:')
except GetoptError as e:
	print('Command line error:', file=stderr)
	print('\t' + e.msg, file=stderr)
	print(usage, file=stderr)
	exit(-1)

if len(args) == 1:
	device_path = args[0]
elif len(args) > 1:
	print(usage, file=stderr)
	exit(0)

for opt, val in optlist:
	if opt == '-t':
		try:
			dump_time = float(val)
		except ValueError as e:
			print('Command line error:', file=stderr)
			print(str(e), file=stderr)
			print(usage, file=stderr)
			exit(-1)
	elif opt == '-v':
		verbose = 1
		verbose_file, bin_file = stdout, None
	elif opt == '-V':
		verbose = 2
		verbose_file, bin_file = stderr, stdout
	elif opt.lower() == '-h':
		print(usage, file=stderr)
		exit(0)

# dump from device

try:
	main()
except FileNotFoundError as e:
	print('Open device file error: ' + str(e), file=stderr)
except KeyboardInterrupt:
	pass
