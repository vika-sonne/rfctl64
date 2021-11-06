#!/usr/bin/env python3

from sys import byteorder, stdin
import argparse
from time import sleep
import statistics
from typing import Iterable, Tuple


# LIRC (Linux Infrared Remote Control) constants
LIRC_VALUE_MASK = 0x00FFFFFF
LIRC_MODE2_MASK = 0xFF000000
LIRC_MODE2_SPACE = 0x00000000
LIRC_MODE2_PULSE = 0x01000000
LIRC_MODE2_TIMEOUT = 0x03000000

DEFAULT_MIN_SAMPLE_LEN = 15

MAX_BIT_TIME, MIN_BIT_TIME, MIN_TIME = 2_000, 1_000, 300 # us
MIN_BITS_COUNT = 15


class Analysis:

	def __init__(self, min_sample_len: int) -> None:
		self.data: list[int] = []
		self.min_sample_len = min_sample_len
		self.last_is_ok = False

	def _print_bits(self, bits: Iterable[Tuple[int, int]]) -> str:
		return ''.join(('1' if x[0] > x[1] else '0' for x in bits))

	def add(self, level: bool, value: int) -> str:
		data = self.data
		if level:
			# add high level
			data.append(value)
		elif any(data):
			# add low level # high level should be first item
			data.append(value)
			# analysis with new data item
			if len(self.data) >= self.min_sample_len:
				bits: Iterable[Tuple[int, int]] = tuple(x for x in zip(data[::2], data[1::2]))
				bits_lens = tuple(sum(x) for x in bits)
				# print(f'{tuple(bits)=}')
				# print(f'{tuple(bits_lens)=}')
				mean, stdev = statistics.mean(bits_lens), statistics.stdev(bits_lens)
				if stdev >= mean:
					# print('del data[0:2]')
					if self.last_is_ok:
						print(self._print_bits(bits))
						data.clear()
					else:
						del data[0:2]
				else:
					self.last_is_ok = True
					# print(self._print_bits(bits))

	def decode(self) -> str:
		if len(self.data) > self.min_sample_len:
			return self._print_bits(self.data)
		return ''

def main():
	analysis = Analysis(args.l)
	fd = stdin if args.f == '-' else open(args.f, 'rb')
	fd_read = fd.read if fd != stdin else fd.buffer.read
	while(True):
		buff = fd_read(4)
		if len(buff) == 4:
			data = int.from_bytes(buff, byteorder)
			mode, value = data & LIRC_MODE2_MASK, data & LIRC_VALUE_MASK
			if mode == LIRC_MODE2_TIMEOUT:
				if args.d:
					print('timeout')
				else:
					print(analysis.decode())
			else:
				if args.d:
					print(f'{"1" if mode == LIRC_MODE2_PULSE else "0"} {value:05d}{" " + buff.hex() if args.D else ""}')
				else:
					if (buff := analysis.add(mode == LIRC_MODE2_PULSE, value)):
						print(buff)
		elif fd != stdin:
			break

# process command-line

def parse_args():
	parser = argparse.ArgumentParser(description='Rfdump analysis tool.')
	parser.add_argument('-l', metavar='SAMPLE_LEN', default=DEFAULT_MIN_SAMPLE_LEN, help=f'Sample length; default: {DEFAULT_MIN_SAMPLE_LEN}')
	parser.add_argument('f', metavar='DUMP_FILE_PATH', help='Dump binary file or stdin; exmple: "rfdump.bin" or "-"')
	parser.add_argument('-d', action='store_true', help='Just dump LIRC samples')
	parser.add_argument('-D', action='store_true', help='As -d but dump also a hex values')
	# parser.add_argument('-v', action='count', default=0, help='verbose level: -v; default: no verbose')
	args = parser.parse_args()
	return args

args = parse_args()
if args.D:
	args.d = True

# analysis of dump from device

try:
	main()
except KeyboardInterrupt:
	pass
