"""Copy canonical runtime modules into the self-contained plugin; --check verifies."""
from pathlib import Path
import sys
root = Path(__file__).resolve().parent.parent
target = root/'plugins/codex-monitor/scripts/runtime'
for name in ('codex_monitor.py', 'remote_monitor.py'):
    source = (root/name).read_bytes()
    if '--check' in sys.argv:
        if not (target/name).exists() or (target/name).read_bytes() != source:
            raise SystemExit('Plugin runtime is stale: '+name)
    else:
        target.mkdir(parents=True, exist_ok=True)
        (target/name).write_bytes(source)
print('Plugin runtime is synchronized')
