
from os.path import join as path_join
from typing import Dict, Optional, NamedTuple


class RfctlSettings:
	'''Settings module.
	Used to load/save tab separated values file.

	Example:
	import RfctlSettings
	RfctlSettings.load() # or .load('path of tsv file')
	if RfctlSettings.key_settings[key_uuid].enabled:
		RfctlSettings.key_settings[key_uuid].enabled = False
	RfctlSettings.save() # or .save('path of tsv file')
	'''

	KEYS_SETTINGS_PATH, KEYS_SETTINGS_FILE_NAME = '.', 'rfctl_keys.tsv'

	class KeyRow(NamedTuple):
		event: str
		enabled: bool

	key_settings: Dict[str, KeyRow] = {}

	@classmethod
	def get_default_file_path(cls) -> str:
		return path_join(cls.KEYS_SETTINGS_PATH, cls.KEYS_SETTINGS_FILE_NAME)

	@classmethod
	def load(cls, settings_file_path: Optional[str] = None):
		if not settings_file_path:
			settings_file_path = cls.get_default_file_path()

		cls.key_settings.clear()
		with open(settings_file_path, 'r') as f:
			while (line := f.readline()):
				line = line.strip()
				if line and not line.startswith('#'):
					line = line.split('\t', maxsplit=3)
					if len(line) > 1:
						cls.key_settings[line[0]] = cls.KeyRow(
							line[1],
							bool(line[2] if len(line) > 2 else False)
						)

	@classmethod
	def save(cls, settings_file_path: Optional[str] = None):
		if not settings_file_path:
			settings_file_path = cls.get_default_file_path()
		with open(settings_file_path, 'w') as f:
			f.write('# KEY_UUID\tEVENT\tENABLED\n')
			for k, v in cls.key_settings.items():
				f.write('{}\t{}\t{}\n'.format(k, v.event, '1' if v.enabled else '0'))


# RfctlSettings.load()
# print(f'{RfctlSettings.key_settings=}')
# RfctlSettings.save()
