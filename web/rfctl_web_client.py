from typing import List, Optional, Dict, Iterable
from browser import document as doc, window, ajax, timer, bind, html
from browser.widgets.dialog import Dialog, InfoDialog
import urllib.parse


class Rfctl:

	def show_error(msg: str):
		dialog = InfoDialog(' Error ', msg, ok='Close')
		window.console.log(f'{dir(dialog)=}')
		dialog.ok_button.focus()

	def build_url(url: str, args: Dict[str, str], args2: Dict[str, str]):
		'gets url address with parameters'
		if not (args or args2):
			return url
		return '{}?{}'.format(
			url,
			'&'.join(('{}={}'.format(k, urllib.parse.quote(str(v))) for k, v in {**args, **args2}.items()))
		)

	def api_call(url: str, args: Dict[str, str] = {}):
		'API call decorator'

		def api_call_decorator(fun):

			def api_call_wrapper(args2: Dict[str, str] = {}):
				req = ajax.ajax()
				req.bind('complete', fun)
				req.open('GET', Rfctl.build_url(url, args, args2), True)
				req.send()
			
			return api_call_wrapper

		return api_call_decorator

	def add_page_header(exclude_menu: Iterable[str] = []):
		# adds page header with ARIA roles: header, main e.t.c.
		header_menu = doc['header_menu']
		if exclude_menu:
			exclude_menu = tuple(x.lower() for x in exclude_menu)
		if 'main' not in exclude_menu:
			header_menu <= html.SPAN('&nbsp;&nbsp;') + html.A('Main', href='/')
		if 'keys' not in exclude_menu:
			header_menu <= html.SPAN('&nbsp;&nbsp;') + html.A('Keys', href='/keys')
		if 'add_key' not in exclude_menu:
			header_menu <= html.SPAN('&nbsp;&nbsp;') + html.A('Add key', href='/add_key')
		if 'about' not in exclude_menu:
			header_menu <= html.SPAN('&nbsp;&nbsp;') + html.A('About', href='/about')

	api_calls: List['ApiCallTimeRefresh'] = []

	@classmethod
	def get_api_call(cls, name: str) -> 'ApiCallTimeRefresh':
		for x in cls.api_calls:
			if x.name == name:
				return x

	class ApiCallTimeRefresh:

		def __init__(self, api_address: str, name: Optional[str] = None, ui_element_id: Optional[str] = None,
				args: Optional[Dict[str, str]] = None, period=5, autostart=True):
			self.period = period
			self.api_address = api_address
			self.name = name
			self.ui_element_id = ui_element_id
			self.args = args
			self.args2: Optional[Dict[str, str]] = None
			self.rest_timer = None
			Rfctl.api_calls.append(self)
			if autostart:
				self.start()

		def read(self, req):
			self.ready(req)
			if self.rest_timer:
				timer.clear_timeout(self.rest_timer)
			if self.period:
				self.rest_timer = timer.set_timeout(self.rest_refresh, self.period * 1000)

		def rest_refresh(self):
			if self.rest_timer:
				timer.clear_timeout(self.rest_timer)
			req = ajax.ajax()
			req.bind('complete', self.read)
			req.open('GET', Rfctl.build_url(self.api_address, self.args, self.args2), True)
			req.send()

		def start(self, args: Optional[Dict[str, str]] = {}):
			self.args2 = args
			self.rest_refresh()

		def stop(self):
			if self.rest_timer:
				timer.clear_timeout(self.rest_timer)
				self.rest_timer = None


window.Rfctl = Rfctl


def build_page_main():

	# status & keys history functions

	class Status(Rfctl.ApiCallTimeRefresh):
		def ready(self, api_answer):
			try:
				data = api_answer.json
			except Exception:
				doc[self.ui_element_id].innerHTML = '❌ CONNECTION ERROR'
			else:
				doc[self.ui_element_id].innerHTML = '{}{}'.format(
					'✅ WORKING' if int(data['code']) == 0 else '❌ NOT WORKING',
					': ' + str(data['output']) if data['output'] else ''
				)

	class KeysHistory(Rfctl.ApiCallTimeRefresh):
		def ready(self, api_answer):
			try:
				data = api_answer.json
			except Exception:
				return
			doc[self.ui_element_id].innerHTML = ''
			for k in data:
				doc[self.ui_element_id] <= html.P(k['key'])

	# page content

	Rfctl.add_page_header(exclude_menu=('main',))

	main = html.MAIN(role='main')
	main <= html.H4(id='status')
	# main <= html.H4('Keys history:')
	# main <= html.P(id='keys_history')
	doc <= main

	Status('/api/status', 'Status', 'status')
	# KeysHistory('/api/keys_history', 'Keys history', 'keys_history', {'l': 5})


Rfctl.build_page_main = build_page_main


def build_page_keys():

	# key delete functions

	@Rfctl.api_call('/api/keys')
	def del_key(api_answer: ajax):
		try:
			data = api_answer.json
		except Exception:
			Rfctl.show_error('Can\'t delete key')
			return
		if data['code'] == 0:
			# key deleted # remove key from keys table
			if (key_name := getattr(Rfctl, 'del_key_name', None)):
				keys_table = doc['keys_table_body']
				for i, r in enumerate(keys_table.rows):
					if r.cells[0].textContent == key_name:
						keys_table.deleteRow(i)
						break
				Rfctl.del_key_name = None
		else:
			d = Dialog(' Key delete error ')
			d.panel <= html.P(f'Code = {data["code"]}')
			d.panel <= html.P(f'{data["output"]}')

	def key_del(key_name):
		if not getattr(Rfctl, 'del_key_name', None):
			Rfctl.del_key_name = key_name
			del_key({'del': key_name})  # send Ajax request

	window.key_del = key_del

	# keys sorting functions

	@Rfctl.api_call('/api/keys')
	def get_keys(api_answer: ajax):
		try:
			data = api_answer.json
		except Exception:
			Rfctl.show_error('Can\'t get keys')
			return
		keys_table = doc['keys_table_body']
		# clear keys table
		while any(keys_table.rows):
			keys_table.deleteRow(0)
		# fill keys table from answer
		for k in data:
			keys_table <= html.TR(
				html.TD(k['key'], Class='keys_table_name')
				+ html.TD(k['dt'], Class='keys_table_dt')
				+ html.TD(k['desc'], Class='keys_table_name')
				+ html.TD(k.get('event'))
				+ html.TD(html.INPUT(type='checkbox', checked=bool(k.get('enabled'))))
				# + html.TD(
				# 	html.BUTTON('🗑', style={'background-color': 'salmon'}, onclick='window.key_del("{}")'.format(k['key'])) +
				# 	html.BUTTON('Disable'), Class='keys_table_control'
				, Class='keys_table_row')

	def keys_list(args):
		if (f := doc['keys_name_filter'].value):
			args['filter_name'] = f
		get_keys(args)  # send Ajax request

	def keys_sort_name(sort_dir: str):
		keys_list({'sort_name': sort_dir})

	window.keys_sort_name = keys_sort_name

	def keys_sort_dt(sort_dir: str):
		keys_list({'sort_dt': sort_dir})

	window.keys_sort_dt = keys_sort_dt

	# page content

	Rfctl.add_page_header(exclude_menu=('keys',))

	main = html.MAIN(role='main')
	keys_table = html.TABLE(id='keys_table')
	keys_table <= html.CAPTION('Keys list', Class='keys_table')
	keys_table <= html.THEAD(
		html.TR(
			html.TD(
				html.INPUT(type='button', Class='keys_table_sort', value='◣', onclick="window.keys_sort_name(\'down\')")
				+ html.INPUT(type='button', Class='keys_table_sort', value='◥', onclick="window.keys_sort_name(\'up\')")
				+ html.SPAN('&nbsp;')
				+ html.INPUT(type='text', id='keys_name_filter', onkeypress="if(event.key==\'Enter\') window.keys_sort_name(\'down\');")
				+ html.INPUT(type='button', Class='keys_table_sort', value='🔎', onclick="window.keys_sort_name(\'down\')")
				, Class='keys_table_head keys_table_sort')
			+ html.TD(
				html.INPUT(type='button', Class='keys_table_sort', value='◣', onclick="window.keys_sort_dt(\'down\')")
				+ html.INPUT(type='button', Class='keys_table_sort', value='◥', onclick="window.keys_sort_dt(\'up\')")
				, Class='keys_table_head')
			+ html.TD(Class='keys_table_head')
			+ html.TD(Class='keys_table_head')
			+ html.TD(Class='keys_table_head')
			, Class='keys_table_head')
		, Class='keys_table')
	keys_table <= html.TBODY(id='keys_table_body')
	main <= keys_table
	doc <= main
	keys_sort_name('down')  # populate keys table # send Ajax request for list keys


Rfctl.build_page_keys = build_page_keys


def build_page_add_key():

	# add key functions

	@Rfctl.api_call('/api/keys')
	def add_key(api_answer: ajax):
		try:
			data = api_answer.json
		except Exception:
			Rfctl.show_error('Can\'t add key')
			return
		add_result = doc['keys_add_result']
		add_result.clear()
		if data['code']:
			add_result <= html.P(f'❌ Code: {data["code"]}')
		else:
			add_result <= html.P('✅')
		if data['output']:
			add_result <= html.P(data['output'])

	def keys_add_key():
		if (f := doc['keys_add_description'].value):
			doc['keys_add_result'].clear()
			doc['keys_add_result'].innerHTML = '<p>⚙ Working ...</p>'
			event, enabled = doc['keys_add_event'].value, doc['keys_add_enabled'].checked
			add_key({'add': f, 'event': event, 'enabled': enabled if event else False})  # send Ajax request

	window.keys_add_key = keys_add_key

	def key_check_desc(e):
		if '"' in e.srcElement.value:
			e.srcElement.classList.add('value_is_invalid')
			doc['keys_add_key_btn'].disabled = True
		else:
			e.srcElement.classList.remove('value_is_invalid')
			doc['keys_add_key_btn'].disabled = False

	window.key_check_desc = key_check_desc

	# page content

	Rfctl.add_page_header(exclude_menu=('add_key',))

	main = html.MAIN(role='main')
	main <= html.P(
		'Key description:'
		+ html.INPUT(type='text', id='keys_add_description', maxlength='100', minlength='1', placeholder='description', oninput='window.key_check_desc(event)')
		+ html.INPUT(type='text', id='keys_add_event', maxlength='100', minlength='1', placeholder='event')
		+ html.INPUT(type='checkbox', id='keys_add_enabled', checked='1')
		+ html.INPUT(type='button', id='keys_add_key_btn', onclick='window.keys_add_key()', value='Scan & add key')
	)
	main <= html.DIV(
		'Result:'
		+ html.DIV(id='keys_add_result')
	)
	doc <= main


Rfctl.build_page_add_key = build_page_add_key


def build_page_about():

	# page content

	# page_about = doc['page_about'].innerHTML
	Rfctl.add_page_header(exclude_menu=('about',))
	# doc.body.innerHTML += page_about

	doc["brython_version"].innerHTML = str(window.__BRYTHON__.__MAGIC__)
	from sys import version as python_version
	doc["python_version"].innerHTML = str(python_version)


Rfctl.build_page_about = build_page_about
