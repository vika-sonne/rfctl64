#!/usr/bin/env python3
# coding=utf-8

from sys import byteorder, stderr
import argparse
from typing import Iterable, Tuple
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from plotly.io import to_html
from os import path


# LIRC (Linux Infrared Remote Control) constants
LIRC_VALUE_MASK = 0x00FFFFFF
LIRC_MODE2_MASK = 0xFF000000
LIRC_MODE2_SPACE = 0x00000000
LIRC_MODE2_PULSE = 0x01000000
LIRC_MODE2_TIMEOUT = 0x03000000

def main():
	data: Iterable[Tuple[int, int]] = []
	start_time, end_time = args.s, args.e
	time_line, time_line_diff = 0, 0 if start_time is None else start_time
	with open(args.f, 'rb') as fd:
		while(True):
			buff = fd.read(4)
			if len(buff) == 4:
				buff = int.from_bytes(buff, byteorder)
				mode, value = buff & LIRC_MODE2_MASK, buff & LIRC_VALUE_MASK
				if mode == LIRC_MODE2_TIMEOUT:
					pass
				else:
					if start_time is not None and time_line < start_time:
						time_line += value
						continue
					if time_line:
						data.append((0 if mode == LIRC_MODE2_PULSE else 1, time_line - 1 - time_line_diff))
					if end_time is not None and time_line >= end_time:
						break
					data.append((1 if mode == LIRC_MODE2_PULSE else 0, time_line - time_line_diff))
					time_line += value
			else:
				fd.close()
				break

	subplot_titles = (args.t if args.t else path.basename(args.f),)
	fig = make_subplots(rows=len(subplot_titles), cols=1, shared_xaxes=True, subplot_titles=subplot_titles)
	fig.add_trace(go.Scatter(
		x=tuple(x[1] for x in data),
		y=tuple(x[0] for x in data),
		),
		row=len(fig.data) + 1, col=1
		)
	fig.update_yaxes(row=len(fig.data), col=1, showticklabels=False)
	fig.update_xaxes(title_text="Time, µs", row=len(fig.data), col=1)
	fig.update_layout(margin=dict(l=0, r=0, t=20, b=0, pad=0))
	if start_time is not None:
		# set time line range
		fig.update_layout(xaxis_range=[0,time_line - start_time if end_time is None else end_time - start_time])
	print(to_html(fig, include_plotlyjs='cdn', full_html=False))

# process command-line

def parse_args():
	parser = argparse.ArgumentParser(
		description='Rfdump graph tool. Makes interactive graph (based on plotly https://plotly.com/python/line-charts/) from binary dump file.',
		epilog='Example:\npython3 rfgraph.py -t "Example of 3 times of key pushing" rfdump.bin > example.htm'
		)
	parser.add_argument('f', metavar='BIN_DUMP_FILE_PATH', help='Binary dump file; example: "rfdump.bin"')
	parser.add_argument('-t', metavar='GRAPH_TITLE', help=f'By default is file name')
	parser.add_argument('-s', metavar='START_TIME', type=int, help=f'Filter by time: start time, µs; example: "-s 2_220_000"')
	parser.add_argument('-e', metavar='END_TIME', type=int, help=f'Filter by time: end time, µs; example: "-e 2_270_000"')
	args = parser.parse_args()
	return args

args = parse_args()

# convert to graph

try:
	main()
except FileNotFoundError as e:
	print(str(e), file=stderr)
except KeyboardInterrupt:
	pass
