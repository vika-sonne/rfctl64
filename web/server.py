
from typing import Dict, Tuple, List, Optional, Union, Iterable, NamedTuple
import sys
from socket import SOCK_STREAM, AI_PASSIVE, getaddrinfo, AddressFamily
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime, timezone
import argparse
from glob import glob
from os.path import join as path_join, abspath, basename, split as path_split, splitext
from os import fstat
import email.utils
from subprocess import getstatusoutput


keys_path = ''
favicon_path = None
page_title = 'Rfctl web server'

class Log:
	INFO, DEBUG, TRACE = 0, 1, 2
	LOG_DEFAULT = INFO

	log_level = LOG_DEFAULT

	@staticmethod
	def info(msg):
		if Log.INFO <= Log.log_level:
			print(datetime.now().strftime('%H:%M.%S.%f ') + str(msg))

	@staticmethod
	def debug(msg):
		if Log.DEBUG <= Log.log_level:
			print(datetime.now().strftime('%H:%M.%S.%f ') + str(msg))

	@staticmethod
	def trace(msg):
		if Log.TRACE <= Log.log_level:
			print(datetime.now().strftime('%H:%M.%S.%f ') + str(msg))

def get_keys_file_names() -> List[str]:
	# process .key files at keys path
	Log.debug(f'Open key files from path "{abspath(keys_path)}":')
	return glob(path_join(keys_path, '*.key'))


class RequestHandler(SimpleHTTPRequestHandler):

	def is_gis(self):
		return self.path.lower().startswith('/gis/')

	def gis(self):
		self.send_response(HTTPStatus.OK)
		self.end_headers()
		self.wfile.write(b'Hello from Odyssey Gis !')

	def send_file_head(self, path: str) -> Optional[object]:
		ctype = self.guess_type(path)
		try:
			f = open(path, 'rb')
		except OSError:
			return None

		try:
			fs = fstat(f.fileno())
			# Use browser cache if possible
			if ("If-Modified-Since" in self.headers
					and "If-None-Match" not in self.headers):
				# compare If-Modified-Since and time of last file modification
				try:
					ims = email.utils.parsedate_to_datetime(
						self.headers["If-Modified-Since"])
				except (TypeError, IndexError, OverflowError, ValueError):
					# ignore ill-formed values
					pass
				else:
					if ims.tzinfo is None:
						# obsolete format with no timezone, cf.
						# https://tools.ietf.org/html/rfc7231#section-7.1.1.1
						ims = ims.replace(tzinfo=timezone.utc)
					if ims.tzinfo is timezone.utc:
						# compare to UTC datetime of last modification
						last_modif = datetime.fromtimestamp(
							fs.st_mtime, timezone.utc)
						# remove microseconds, like in If-Modified-Since
						last_modif = last_modif.replace(microsecond=0)

						if last_modif <= ims:
							self.send_response(HTTPStatus.NOT_MODIFIED)
							self.end_headers()
							f.close()
							return None

			self.send_response(HTTPStatus.OK)
			self.send_header("Content-type", ctype)
			self.send_header("Content-Length", str(fs[6]))
			self.send_header("Last-Modified",
				self.date_time_string(fs.st_mtime))
			self.end_headers()
			return f
		except:
			f.close()
			raise

	def send_file_body(self, f: Optional[object]):
		if f:
			try:
				self.copyfile(f, self.wfile)
			finally:
				f.close()

	def send_html(self, html: str):
		html = html.encode('utf-8')
		# send headers
		self.send_response(200)
		self.send_header('Content-type', 'text/html; charset=utf-8')
		self.send_header("Content-Length", len(html))
		self.end_headers()
		# send body
		self.wfile.write(html)

	def _send_main(self, main: str, title_suffix=''):
		buff = '<html><head><title>{}{}</title><link rel="stylesheet" href="/main.css"></head><body>'.format(
			page_title if page_title else '',
			' - ' + title_suffix if title_suffix else ''
			)
		buff += '<header role="banner"><h1>Rfctl</h1><span class="header-menu">'
		buff += '<a href="/">Main</a>&nbsp;&nbsp;&nbsp;'
		buff += '<a href="/keys">Keys</a>&nbsp;&nbsp;&nbsp;'
		buff += '</span></header>'
		buff += '<main role="main">' + main + '</main>'
		buff += '<footer role="contentinfo">'
		buff += '<p>Version: &lt;UNKNOWN VERSION&gt;</p>'
		buff += '</footer></body></html>'
		self.send_html(buff)

	def do_GET(self):
		Log.debug('GET {}'.format(self.path))
		Log.trace(vars(self))
		if self.path == '/':
			buff = ''
			self._send_main(buff, 'Main')
		elif self.path == '/main.css':
			f = self.send_file_head('./main.css')
			self.send_file_body(f)
		elif self.path == '/keys':
			buff = '<a href="/read_key">Read key</a>'
			buff += '<p>Keys:<p>'
			if keys_path:
				keys_filenames = get_keys_file_names()
				for kf in keys_filenames:
					buff += '{}<br/>'.format(basename(kf))
			self._send_main(buff, 'Keys')
		elif self.path == '/read_key':
			key_file_name = 'New key.key'
			exitcode, output = getstatusoutput(f'read_key.sh {path_join(abspath(keys_path), key_file_name)}')
			if exitcode:
				# error happened while reading key
				buff = f'<p><b>Error happened while reading key:</b><br/>{output}</p>'
				buff += '<a href="/read_key">Read key again</a>'
			else:
				match_keys = set()
				for key_name in output.splitlines():
					if key_name != 'tmp.key':
						match_keys.add(key_name)
				if match_keys:
					buff = f'<p>New key match with existing keys:<br/><b>{", ".join(match_keys)}</b></p>'
				else:
					buff = f'<p>New key added:<br/><b>{key_file_name}</b></p>'
			self._send_main(buff, 'Keys')
		elif self.path == '/favicon.ico':
			if favicon_path:
				f = self.send_file_head(favicon_path)
				self.send_file_body(f)
		Log.debug('done')

	def do_HEAD(self):
		Log.debug('HEAD')
		Log.debug(vars(self))
		if self.is_gis():
			Log.debug('GIS')
		else:
			SimpleHTTPRequestHandler.do_HEAD(self)
		Log.debug('done')


class SystemInfoHandler:
	@classmethod
	def instance(cls) -> Optional[SystemInfoHandler]:
		try:
			import psutil
		except ModuleNotFoundError:
			return None

class PythonMemoryHandler:
	def __init__(self):
		pass
	def get_main(self) -> str:
		sum1 = self.tracker
	@classmethod
	def instance(cls) -> Optional[PythonMemoryHandler]:
		try:
			from pympler import tracker
			cls.tracker = tracker.SummaryTracker()
		except ModuleNotFoundError:
			return None


def http_server(bind_address=None, bind_port=8000):

	try:
		from pympler import summary
	except ModuleNotFoundError:
		pass

	PROTOCOL = "HTTP/1.0"

	def get_best_family(*address) -> Tuple[AddressFamily, Tuple[str, int]]:
		infos = getaddrinfo(*address, type=SOCK_STREAM, flags=AI_PASSIVE)
		family, type_, proto, canonname, sockaddr = next(iter(infos))
		return family, sockaddr

	ThreadingHTTPServer.address_family, addr = get_best_family(bind_address, bind_port)
	RequestHandler.protocol_version = PROTOCOL
	with ThreadingHTTPServer(addr, RequestHandler) as httpd:
		host, bind_port = httpd.socket.getsockname()[:2]
		url_host = f'[{host}]' if ':' in host else host
		Log.info(
			f'Start HTTP server on {host}:{bind_port} '
			f'(http://{url_host}:{bind_port}/) ...'
		)
		try:
			httpd.serve_forever()
		except KeyboardInterrupt:
			Log.info('Keyboard interrupt received, exiting.')
			sys.exit(0)

def parse_args():
	parser = argparse.ArgumentParser(
		description='Rfctl web server.',
		epilog='Example:\npython3 server.py ../keys'
		)
	parser.add_argument('k', metavar='KEYS_PATH', help='Keys files path')
	parser.add_argument('-a', metavar='ADDRESS', help='Listen IP address')
	parser.add_argument('-p', metavar='PORT', help='Listen IP/TCP port')
	parser.add_argument('-t', metavar='PAGE_TITLE', help='Pages title')
	parser.add_argument('-f', metavar='IMAGE_FILE_PATH', help='Path to favicon.ico file')
	parser.add_argument('-v', action='count', help='verbose')
	args = parser.parse_args()
	return args

args = parse_args()

keys_path = args.k
favicon_path = args.f
if args.t:
	page_title = args.t
Log.info(f'{page_title=}')

if args.v == 1:
	Log.log_level = Log.DEBUG
elif args.v > 1:
	Log.log_level = Log.TRACE


http_server()
