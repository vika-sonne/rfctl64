#!/usr/bin/env sh

if [ $# -eq 0 -o "$1" = "-h" ]; then
	echo "Scans 433MHz RF & stores to LIRC 4-bytes sequence .bin file\n\nUsage:\n$0 <.bin file path>\n\nUse environment variables:\nRFCTL_PYTHON_PATH default: ."
	exit 254
fi

if [ $# -gt 1 ]; then
	RFCTL_BIN_FILE_PATH="$(realpath $1)/rfctl.bin"
	RFCTL_KEY_FILE_PATH="$(realpath $1)/rfctl.key"
else
	RFCTL_BIN_FILE_PATH="/tmp/rfctl.bin"
	RFCTL_KEY_FILE_PATH="/tmp/rfctl.key"
fi

rfctl_python_path=$(realpath ${RFCTL_PYTHON_PATH:-.})

rfctl_keys_path=${RFCTL_KEYS_PATH:-keys}

python3 "${rfctl_python_path}/rfdump.py" -t 0.5 > "$RFCTL_BIN_FILE_PATH" &&
	python3 "${rfctl_python_path}/rfanalysis.py" -k "$RFCTL_BIN_FILE_PATH" > "$RFCTL_KEY_FILE_PATH" &&
	cat "$RFCTL_BIN_FILE_PATH" | python3 "${rfctl_python_path}/rfdetect.py" -k "$rfctl_keys_path" -f "$RFCTL_KEY_FILE_PATH" - &&
	mv "$RFCTL_KEY_FILE_PATH" "$(realpath $rfctl_keys_path)/$1" &&
	rm "$RFCTL_BIN_FILE_PATH"
