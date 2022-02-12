from bottle import route, run, static_file as bottle_static_file, request, response
from bottle import __version__ as bottle_version
from datetime import datetime
from os.path import join as path_join, abspath, dirname, basename, splitext
from os import remove as os_remove
import psutil
import platform
from subprocess import getstatusoutput
from glob import glob
from typing import Tuple, Optional, Iterable
from re import compile as re_compile
from uuid import uuid4
from settings import RfctlSettings


page_title = 'Rfctl web server'

python_files_path = abspath(path_join(dirname(abspath(__file__)), '..'))
bash_files_path = abspath(path_join(dirname(abspath(__file__)), '..'))
keys_files_path = abspath(path_join(dirname(abspath(__file__)), '../keys'))
static_files_path = dirname(abspath(__file__))
static_files = (
	'favicon.ico',
	'brython.js',
	'brython_stdlib.js',
	'plotly.min.js',
	'rfctl_web_client.py',
	'rfctl_web_client.css',
)
favicon_path = ''


def escape_json(buff: str) -> str:
	return buff.replace('\n', '\\n').replace('"', '\\"')


def get_keys(filter_name: Optional[str]=None, filter_dt: Optional[str]=None) -> Iterable[Tuple[str, str, str]]:
	# process .key files at keys path. Returns tuple: key name, key date time, key description
	ret = []
	fpath = path_join(keys_files_path, ('*' + filter_name + '*' if filter_name else '*') + '.key')
	for fpath in sorted(glob(fpath)):
		key_dt, key_desc = '', ''
		with open(fpath, 'r') as f:
			for line in f.readlines():
				if line.startswith('#@'):
					key_dt = line[2:30].strip()
				elif line.startswith('#!desc='):
					key_desc = line[7:].strip()
				elif not line.startswith('#'):
					ret.append(tuple((splitext(basename(fpath))[0], key_dt, key_desc)))
					break
	return ret


key_file_re = re_compile('^[0-9a-f]{32}$')  # filter for .key file name validation


def is_key_file_name_correct(fname: str) -> bool:
	return bool(key_file_re.match(fname))


def get_new_key_file_name() -> str:
	return uuid4().hex + '.key'


def is_key_description_correct(desc: str) -> bool:
	return not '"' in desc


@route('/static/<filename>')
def static_file(filename: str) -> Optional[str]:
	if filename in static_files:
		return bottle_static_file(filename, root=static_files_path)


@route('/favicon.ico')
def favicon():
    return ("/static/favicon.ico")


def set_keys_settings(key_uuid: str, event: Optional[str] = None, enabled: Optional[bool] = None):

	def set_settings(ks: RfctlSettings.KeyRow):
		if event is not None:
			ks.event = event
		if enabled is not None:
			ks.enabled = enabled

	if (ks := RfctlSettings.key_settings.get(key_uuid)):
		set_settings(ks)
	else:
		# create settings for a new key
		ks = RfctlSettings.KeyRow
		set_settings(ks)
		RfctlSettings.key_settings[key_uuid] = ks
	RfctlSettings.save()


def del_keys_settings(key_uuid: str):
	try:
		del RfctlSettings.key_settings[key_uuid]
	except KeyError:
		return
	RfctlSettings.save()


# pages handlers


def get_regular_page(title_suffix='', page_build_fun='', load_plotly=False, body: Optional[str] = None):
	# Gets regular page with ARIA roles: header, main e.t.c.
	buff = '''<html><head>
		<title>{}</title>
		<link rel="stylesheet" href="/static/rfctl_web_client.css">
		<script src="/static/brython.js"></script>
		<script src="/static/brython_stdlib.js"></script>
		<script src="/static/rfctl_web_client.py" type="text/python"></script>
		{}
		</head><body onload="brython()">'''.format(
		' - '.join((page_title, title_suffix)),
		'<script src="/static/plotly.min.js"></script>' if load_plotly else ''
	)
	buff += '<body>'
	buff += '<header role="banner">Rfctl<span id="header_menu" class="header-menu"/></header>'
	buff += '<main role="main" id="page_main">'
	if body:
		buff += body
	buff += '''<script type="text/python">
	from browser import window
	window.Rfctl.{}()
	</script>'''.format(page_build_fun)
	buff += '</main></body></html>'
	return buff


@route('/')
def page_main():
	return get_regular_page('', 'build_page_main')


@route('/keys')
def page_keys():
	return get_regular_page('Keys', 'build_page_keys')


@route('/add_key')
def page_add_key():
	return get_regular_page('Add key', 'build_page_add_key')


@route('/about')
def page_about():
	buff = ''
	buff += '<table id="page_about"><tr><td class="about-section" colspan="2">Host</td></tr>'
	buff += f'<tr><td class="about-name">System</td><td class="about-value">{platform.system()}</td></tr>'
	buff += f'<tr><td class="about-name">Version</td><td class="about-value">{platform.version()}</td></tr>'
	buff += f'<tr><td class="about-name">Release</td><td class="about-value">{platform.release()}</td></tr>'
	buff += f'<tr><td class="about-name">Machine</td><td class="about-value">{platform.machine()}</td></tr>'
	buff += f'<tr><td class="about-name">Processor</td><td class="about-value">{platform.processor()}</td></tr>'
	buff += f'<tr><td class="about-name">Node</td><td class="about-value">{platform.node()}</td></tr>'
	buff += f'<tr><td class="about-name">Start time</td><td class="about-value">{datetime.fromtimestamp(psutil.boot_time())}</td></tr>'
	buff += '<tr><td></td><td></td></tr>'
	buff += f'<tr><td class="about-name">Bottle</td><td class="about-value">{bottle_version}</td></tr>'
	buff += '<tr><td></td><td></td></tr>'
	buff += '<tr><td class="about-section" colspan="2">Client</td></tr>'
	buff += '<tr><td class="about-name">Brython</td><td class="about-value" id="brython_version"></td></tr>'
	buff += '<tr><td class="about-name">Python</td><td class="about-value" id="python_version"></td></tr>'
	buff += '</table>'
	return get_regular_page('About', 'build_page_about', body=buff)


# API handlers


@route('/api/uname')
def api_uname() -> str:
	buff = platform.uname()
	return '{{"system":"{},"node":"{}","release":"{}","version":"{}","machine":"{}","processor":"{}"}}'.format(
		buff.system, buff.node, buff.release, buff.version, buff.machine, buff.processor
	)


@route('/api/start_time')
def api_start_time():
	response.content_type = 'application/json'
	return '{{"start_time":{}}}'.format(datetime.fromtimestamp(psutil.boot_time()))


@route('/api/status')
def api_status():
	response.content_type = 'application/json'
	exitcode, output = getstatusoutput(path_join(bash_files_path, 'status.sh'))
	return '{{"code":{},"output":"{}"}}'.format(str(exitcode), str(output))


@route('/api/keys_history')
def api_keys_history():
	'List keys'
	list_start, list_len = request.params.get('s', default=0, type=int), request.params.get('l', default=200, type=int)
	response.content_type = 'application/json'
	buff = '[{}]'.format(
		','.join('{{"key":"{}"}}'.format(x) for x in get_keys()[list_start:list_start + list_len])
	)
	return buff


@route('/api/keys')
def api_keys():
	'Keys operation: list, scan & add, delete'
	add_key_desc, delete_key_name = request.params.get('add'), request.params.get('del')
	response.content_type = 'application/json'
	if add_key_desc:
		# scan & add key with description and name = UUID
		if is_key_description_correct(add_key_desc):
			add_key_name = get_new_key_file_name()
			cmd = 'export RFCTL_PYTHON_PATH="{}" RFCTL_KEYS_PATH="{}"; "{}" "{}" "{}"'.format(
				python_files_path,
				keys_files_path,
				path_join(bash_files_path, 'scan_and_add_key.sh'),
				add_key_name,
				add_key_desc
			)
			print(cmd)
			exitcode, output = getstatusoutput(cmd)
			if exitcode == 0:
				add_key_event, add_key_enabled = request.params.get('event'), request.params.get('enabled')
				set_keys_settings(add_key_name[:-4], add_key_event, add_key_enabled)
		else:
			exitcode, output = '1', 'Key description is incorrect'
		buff = '{{"code":{},"output":"{}"}}'.format(str(exitcode), escape_json(str(output)))
	elif delete_key_name:
		# delete key
		if is_key_file_name_correct(delete_key_name):
			try:
				fpath = path_join(keys_files_path, delete_key_name + '.key')
				print('rm "{}"'.format(fpath))
				os_remove(fpath)
				exitcode, output = 0, ''
				del_keys_settings(delete_key_name)
			except Exception as e:
				exitcode, output = 2, str(e)
		else:
			exitcode, output = 1, 'Incorrect key name: ' + delete_key_name
		buff = '{{"code":{},"output":"{}"}}'.format(str(exitcode), escape_json(str(output)))
	else:
		# get keys list
		list_start, list_len = request.params.get('s', default=0, type=int), request.params.get('l', default=50, type=int)
		sort_name, sort_dt = request.params.get('sort_name', default='down'), request.params.get('sort_dt')
		filter_name, filter_dt = request.params.get('filter_name'), request.params.get('filter_dt')
		keys = sorted(
			get_keys(filter_name, filter_dt)[list_start:list_start + list_len],
			reverse=sort_dt == 'up' if sort_dt else sort_name == 'up',
			key=lambda x: x[1] if sort_dt else x[0])
		buff = '[{}]'.format(
			','.join('{{"key":"{}","dt":"{}","desc":"{}","event":"{}","enabled":"{}"}}'.format(
				x[0], x[1], x[2],
				RfctlSettings.key_settings[x[0]].event if x[0] in RfctlSettings.key_settings else '',
				RfctlSettings.key_settings[x[0]].enabled if x[0] in RfctlSettings.key_settings else ''
				) for x in keys)
		)
	return buff


if __name__ == "__main__":
	# load settings
	RfctlSettings.load()
	# start server
	use_https, debug_server = False, True
	run_args = {
		'host': '0.0.0.0',
		'port': 8080,
	}
	if debug_server:
		run_args.update({
			'debug': True,
			'reloader': True,
		})
	if use_https:
		from bottle import CherootServer
		run_args = {
			'keyfile': '../sertificates/key.pem',
			'certfile': '../sertificates/cert.pem',
			'server': CherootServer,
		}
	run(**run_args)
