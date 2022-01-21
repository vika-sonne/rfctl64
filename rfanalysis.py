#!/usr/bin/env python3

from sys import byteorder, stdin, stderr, stdout
import argparse
from time import sleep
from datetime import datetime
from statistics import quantiles #, mean, stdev
from typing import Iterable, List, Tuple, Optional


# LIRC (Linux Infrared Remote Control) constants
LIRC_VALUE_MASK = 0x00FFFFFF
LIRC_MODE2_MASK = 0xFF000000
LIRC_MODE2_SPACE = 0x00000000
LIRC_MODE2_PULSE = 0x01000000
LIRC_MODE2_TIMEOUT = 0x03000000

DEFAULT_MIN_SAMPLE_LEN = 15

MIN_BITS_COUNT = 22

verbose_fd, dump_fd = None, stdout

class Analysis:

	def __init__(self, min_sample_len: int):
		# filter parameters
		self.min_sample_len = min_sample_len
		self.max_range = 7 # maximum bit times range
		self.sequences = [] # detected bit sequences
		self.peak_koeff = .1 # peak filter koefficient (quantile - peak), %
		# operational variables
		self.is_first_detection = True
		self.last_is_ok = False
		self.last_level_diff = 0
		# bit times: list of tuple(delta %, tuple(bit times))
		self.bit_times: List[Tuple[float, Tuple[int]]] = []

	@classmethod
	def _get_sequence_as_key(cls, sequence: Tuple[float, Tuple[int]], description: Optional[str] = None) -> str:
		return '#@{}\n{}#!delta={:.1%}\n{}'.format(
			datetime.utcnow().isoformat(timespec='seconds'),
			'#!desc=' + description + '\n' if description else '',
			sequence[0],
			"\n".join(('0 ' if i % 2 else '1 ') + str(int(round(x))) for i , x in enumerate(sequence[1]))
			)

	@classmethod
	def _calc_bi_timed_sequences(cls, sequence: Iterable[int]) -> Tuple[float, float, Tuple[int], Tuple[int]]:
		'returns short & long quantiles, short & long bit times sequences'
		q = quantiles(sequence, n=3)
		q_low, q_high = q[0], q[1] # short & long bit times quantiles
		s_low, s_high = [], [] # short & long bit times sequence
		for x in sequence:
			if abs(1 - x / q_low) < abs(1 - x / q_high):
				s_low.append(x)
			else:
				s_high.append(x)
		return q_low, q_high, s_low, s_high

	@classmethod
	def _calc_max_diff(cls, sequence: Iterable[int]) -> float:
		'returns max delta of bit times of sequence, %'
		q_low, q_high, s_low, s_high = cls._calc_bi_timed_sequences(sequence)
		return max((max(s_low) - min(s_low)) / q_low, (max(s_high) - min(s_high)) / q_high)

	@classmethod
	def _calc_avg_sequence(cls, sequence: Iterable[int]) -> Tuple[int]:
		'returns max delta of bit times of sequence, %'
		q_low, q_high, _, _ = cls._calc_bi_timed_sequences(sequence)
		ret = []
		for x in sequence:
			if abs(1 - x / q_low) < abs(1 - x / q_high):
				ret.append(q_low)
			else:
				ret.append(q_high)
		return tuple(ret)

	# def is_single_timed(self) -> Tuple[bool, float]:
	# 	bit_times = self.bit_times
	# 	# check for bits time range
	# 	bit_times_min, bit_times_max = min(bit_times), max(bit_times)
	# 	if bit_times_max / bit_times_min > self.max_range:
	# 		return False, 0
	# 	bits: Iterable[Tuple[int, int]] = tuple(x for x in zip(bit_times[::2], bit_times[1::2]))
	# 	bits_lens = tuple(sum(x) for x in bits)
	# 	mean, stdev = mean(bits_lens), stdev(bits_lens)
	# 	return stdev < mean, stdev / mean

	def is_bi_timed(self) -> Tuple[bool, float]:
		bit_times = self.bit_times
		# check for bits time range
		bit_times_min, bit_times_max = min(bit_times), max(bit_times)
		if bit_times_max / bit_times_min > self.max_range:
			return False, 0
		# check for bits time distribution - it should be only two quantiles
		q = quantiles(bit_times, n=5)
		x_prev, levels_count, max_level_diff = q[0], 0, None
		for x in q[1:]:
			level_diff = x / x_prev
			if max_level_diff is None:
				max_level_diff = level_diff
			if level_diff > 1.07:
				# there is one more level
				if levels_count > 0:
					# and this is third level
					return False, 0
				x_prev = x
				levels_count += 1
			elif level_diff > max_level_diff:
				max_level_diff = level_diff
		# check for two quantiles
		if levels_count != 1:
			return False, 0
		# check for bits time peaks
		if bit_times_min < q[0] * (1 - self.peak_koeff) or bit_times_max > q[-1] * (1 + self.peak_koeff):
			return False, 0
		if verbose_fd:
			print(f'{len(self.sequences)} {bit_times_max / bit_times_min=} {q=} {bit_times=}', file=verbose_fd)
		return True, self._calc_max_diff(bit_times)

	def add(self, level: bool, value: int) -> Optional[str]:
		'returns key (str) if new bit times sequence added'
		ret = None
		bit_times = self.bit_times
		if level:
			# add high level
			bit_times.append(value)
		elif any(bit_times):
			# add low level # high level should be first item
			bit_times.append(value)
			# analysis with new bit_times item
			if len(bit_times) >= self.min_sample_len:
				filter_ok, level_diff = self.is_bi_timed()
				# filter_ok = self.is_single_timed()
				if filter_ok:
					# current sequence is ok
					self.last_is_ok, self.last_level_diff = True, level_diff
				else:
					# current sequence is not ok after this level & value added
					if self.last_is_ok:
						# found key sequence - without this level & value
						self.last_is_ok = False
						if self.is_first_detection:
							self.is_first_detection = False
						else:
							self.sequences.append((self.last_level_diff, tuple(bit_times[:-2])))
							ret = self._get_sequence_as_key(self.sequences[-1])
						bit_times.clear()
					else:
						# searching
						del bit_times[0:2]
		return ret

	def get_sequence(self, description: Optional[str] = None) -> Optional[list]:
		# get sequences with nearest to max(quantiles) of bits count
		q = quantiles((len(x[1]) for x in self.sequences))
		seq_len = int(max(q))
		if verbose_fd:
			print(f'{q=} {seq_len=}\t{",".join((str(len(x[1])-seq_len)+" " +str(i) for i, x in enumerate(self.sequences)))}', file=verbose_fd)
		sequence_indexes = sorted(
			((i, len(x[1]) - seq_len, x[0]) for i, x in enumerate(self.sequences) if len(x[1]) - seq_len >= 0),
			key=lambda x: x[1]
			)
		# get sequence with minimum difference of bits time
		sequence_index = sorted(
			(x for x in sequence_indexes if x[1] == sequence_indexes[0][1]),
			key=lambda x: x[2]
			)[0][0]
		if verbose_fd:
			print(f'{sequence_index=} {tuple(x for x in sequence_indexes if x[1] == sequence_indexes[0][1])=}', file=verbose_fd)
		return self._get_sequence_as_key(
			(self.sequences[sequence_index][0], self._calc_avg_sequence(self.sequences[sequence_index][1])),
			description
			)

	def clear(self):
		self.bit_times.clear()
		self.sequences.clear()
		self.is_first_detection = True
		self.last_is_ok = False
		self.last_level_diff = 0

def main():
	start_time, end_time = args.s, args.e
	analysis = Analysis(args.l)
	fd = stdin if args.f == '-' else open(args.f, 'rb')
	fd_read = fd.read if fd != stdin else fd.buffer.read
	time_line, time_line_diff = 0, 0 if start_time is None else start_time
	while(True):
		buff = fd_read(4)
		if len(buff) == 4:
			bit_times = int.from_bytes(buff, byteorder)
			mode, value = bit_times & LIRC_MODE2_MASK, bit_times & LIRC_VALUE_MASK
			if mode == LIRC_MODE2_TIMEOUT:
				if args.d:
					print('LIRC timeout', file=stderr)
				else:
					analysis.clear()
			else:
				if start_time is not None and time_line < start_time:
					time_line += value
					continue
				if args.d:
					print(f'{"{:07_} ".format(time_line - time_line_diff)}{"1" if mode == LIRC_MODE2_PULSE else "0"} {value:06_d}{" " + buff.hex() if args.D else ""}')
				elif args.b:
					stdout.buffer.write(buff)
				else:
					if (buff := analysis.add(mode == LIRC_MODE2_PULSE, value)):
						if dump_fd:
							print(buff.replace('\n', ', '), file=dump_fd)
				if end_time is not None and time_line >= end_time:
					break
				time_line += value
		elif fd != stdin:
			if args.k:
				try:
					print(analysis.get_sequence(args.k))
				except:
					fd.close()
					exit(-1)
			break

# process command-line

def parse_args():
	parser = argparse.ArgumentParser(
		description='Rfdump analysis tool. Helps coding schemes snalysis from binary dump file.',
		epilog='Example:\npython3 rfanalysis.py rfdump.bin -k "Key description" > 1.key'
		)
	parser.add_argument('f', metavar='BIN_DUMP_FILE_PATH', help='Dump binary file or stdin; example: "rfdump.bin" or "-"')
	parser.add_argument('-l', metavar='SAMPLE_LEN', default=DEFAULT_MIN_SAMPLE_LEN, type=int, help=f'Sample length; default: {DEFAULT_MIN_SAMPLE_LEN}')
	parser.add_argument('-b', action='store_true', help='Dump LIRC samples as binary; useful with -s & -e options')
	parser.add_argument('-d', action='store_true', help='Just dump LIRC samples with time line stamps; useful with -s & -e options')
	parser.add_argument('-D', action='store_true', help='As -d but dump also a hex values')
	parser.add_argument('-s', metavar='START_TIME', type=int, help=f'Filter by time: start time, µs; example: "-s 2_220_000"')
	parser.add_argument('-e', metavar='END_TIME', type=int, help=f'Filter by time: end time, µs; example: "-e 2_270_000"')
	parser.add_argument('-k', metavar='DESCRIPTION', help='Print detected sequene to stdout as key file with description')
	parser.add_argument('-v', action='store_true', help='verbose')
	args = parser.parse_args()
	return args

args = parse_args()
if args.D:
	args.d = True

if args.v:
	verbose_fd = stderr

if args.k:
	dump_fd = None

# analysis of dump from device

try:
	main()
except FileNotFoundError as e:
	print(str(e), file=stderr)
except KeyboardInterrupt:
	pass
