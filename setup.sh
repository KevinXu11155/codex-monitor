#!/bin/sh
set -eu
monitor_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
monitor_python=${1:-python3}
"$monitor_python" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
"$monitor_python" -m venv "$monitor_dir/.venv"
"$monitor_dir/.venv/bin/python" -m pip install "$monitor_dir[remote]"
printf '%s\n' "Installed: $monitor_dir/codex-monitor" "In the existing remote session, run: $monitor_dir/codex-monitor attach --check"
