#!/usr/bin/env python3
"""Portable plugin entry point; keeps the dependency venv outside plugin cache."""
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    if sys.version_info < (3, 11):
        raise SystemExit('Codex Monitor requires Python 3.11+')
    cache = Path(os.environ.get('CODEX_MONITOR_CACHE', str(Path.home()/'.cache/codex-monitor'))).expanduser()
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    if cache.stat().st_uid != os.getuid() or cache.stat().st_mode & 0o077:
        raise SystemExit('Runtime cache must be owned by you with permissions 700: '+str(cache))
    version = f'ws17.1-py{sys.version_info.major}.{sys.version_info.minor}'
    envdir = cache/version
    python = envdir/'bin/python'
    with (cache/'install.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        marker = envdir/'.ready'
        if not marker.exists() or not python.exists():
            print('Preparing Codex Monitor Python runtime (websockets 17.1)...', file=sys.stderr, flush=True)
            venv.EnvBuilder(with_pip=True).create(envdir)
            subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir', 'websockets==17.1'], check=True, stdout=sys.stderr)
            marker.touch(mode=0o600)
    if sys.argv[1:] == ['--bootstrap-only']:
        print(str(python))
        return
    runtime = Path(__file__).resolve().parent/'runtime/remote_monitor.py'
    os.execv(str(python), [str(python), str(runtime), *sys.argv[1:]])


if __name__ == '__main__':
    main()
