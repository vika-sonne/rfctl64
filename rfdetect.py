#!/usr/bin/env python3

from sys import argv, byteorder, stdin, stdout, exit, stderr
from getopt  import getopt, GetoptError
from glob import glob
from os.path import join as path_join, abspath, basename
from time import time


# LIRC (Linux Infrared Remote Control) constants
LIRC_VALUE_MASK = 0x00FFFFFF
LIRC_MODE2_MASK = 0xFF000000
LIRC_MODE2_SPACE = 0x00000000
LIRC_MODE2_PULSE = 0x01000000
LIRC_MODE2_TIMEOUT = 0x03000000

device_path = '/dev/rfctl' # for <device> command-line option
keys_path = './keys' # for <device> command-line option
key_path = None # key file
key_time_tolerance = .15 # koefficient
verbose = 0 # verbose level for -v & -V command-line options
dump_file, verbose_file = stdin, None # file descriptors for input dump binary file & verbose messages

usage = f'''
Detect from device or binary dump file. Detection patterns read from .key files. Key file is space separated values text table; row is level & time (according LIRC dumps).

Usage: python3 {argv[0]} -v -k <path to .key files> -f <.key file>
	-v                     verbose
	<path to .key files>   default: "{keys_path}"
	<.key file>            key file path; used to check .key file
	<device>               path to device; default: {device_path}

Examples:
	python3 {argv[0]}
	cat rfdump.bin | python3 {argv[0]} -v -
'''

def main():

	def load_keys() -> dict:

		def get_level_index(line: list) -> int:
			for i, field in enumerate(line):
				if field in ('0', '1'):
					if len(line) > i + 1:
						return i
			raise Exception('Key file line parse error: ' + ' '.join(line))

		def process_key_file(file_path: str):
			try:
				fd = open(file_path, 'r')
				bits = []
				level_field_index = None
				while (line := fd.readline(100)):
					# process .key file line
					line = line.strip()
					if line.startswith('#'):
						# it comment line # skip
						continue
					line = line.split(' ')
					if level_field_index is None:
						level_field_index = get_level_index(line)
					if line[level_field_index] not in ('0', '1'):
						raise Exception(f'Expected 0 or 1 but given "{line[level_field_index]}" in line: ' + ' '.join(line))
					bits.append((0 if line[level_field_index] == '0' else 1, int(line[level_field_index + 1])))
				ret[basename(file_path)] = tuple(bits)
			except Exception as e:
				print(f'Skip key file "{abspath(file_path)}" due to parsing error: ' + str(e), file=stderr)

		# process .key files at keys path
		ret = {}
		if verbose_file:
			print(f'Open key files from path "{abspath(keys_path)}":', file=verbose_file)
		key_files = glob(path_join(keys_path, '*.key'))
		for kf_index, kf in enumerate(key_files):
			# process .key file line by line
			if verbose_file:
				print(f'{kf_index + 1:02} {basename(kf)}', file=verbose_file)
			process_key_file(kf)

		# process .key file
		if key_path:
			if verbose_file:
				print(f'Open key file "{abspath(key_path)}":', file=verbose_file)
			process_key_file(key_path)

		return ret

	def detect_key(input_bits: list, key_bits: tuple) -> bool:
		if len(input_bits) >= len(key_bits):
			for input_bit, key_bit in zip(input_bits, key_bits):
				if input_bit[0] != key_bit[0] or not key_bit[1] * bit_time_k_low <= input_bit[1] <= key_bit[1] * bit_time_k_high:
					return False
			return True
		return False

	# list of keys, key is tuple of bits, bit is tuple of level (low/high) & time length (us)
	detection_keys: dict[str,tuple[tuple[int,int]]] = load_keys()
	if not detection_keys or not any(detection_keys):
		print('No any keys to detection. Exit', file=stderr)
		exit(-1)

	# process LIRC 4-bytes sequence from device file or stdin
	sample_len_max = max(len(v) for v in detection_keys.values())
	if verbose_file:
		print(f'Max of sample len={sample_len_max}', file=verbose_file)
	if device_path != '-':
		fd = open(device_path, 'rb')
		fd_read = fd.read
	else:
		fd_read = dump_file.buffer.read
	bits = [] # recieved bits
	bit_time_k_low, bit_time_k_high = 1 - key_time_tolerance, 1 + key_time_tolerance
	if verbose_file:
		print('READY', file=verbose_file)
	while(True):
		buff = fd_read(4)
		if len(buff) == 4:
			if verbose > 1 and verbose_file:
				print(buff.hex(), file=verbose_file)
			buff = int.from_bytes(buff, byteorder)
			mode, value = buff & LIRC_MODE2_MASK, buff & LIRC_VALUE_MASK
			if mode == LIRC_MODE2_TIMEOUT:
				pass
			else:
				bits.append((1 if mode == LIRC_MODE2_PULSE else 0, value))
				if len(bits) > sample_len_max:
					del bits[0]
				# compare recieved bits with keys
				for k, v in detection_keys.items():
					if detect_key(bits, v):
						print(k)
						if verbose_file:
							print('\tbits: ', end='', file=verbose_file)
							print(bits, file=verbose_file)
							print('\tkey:  ', end='', file=verbose_file)
							print(v, file=verbose_file)
						bits.clear()
		elif device_path == '-':
			break

# process command-line

try:
	optlist, args = getopt(argv[1:], 'hHvk:f:')
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
	if opt == '-k':
		keys_path = val
	elif opt == '-f':
		key_path = val
	elif opt == '-v':
		verbose += 1
		verbose_file = stdout
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
