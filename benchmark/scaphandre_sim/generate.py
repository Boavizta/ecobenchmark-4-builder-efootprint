"""Generate fake RAPL counters on Linux tmpfs, then run the unchanged exporter."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

root = Path('/tmp/scaphandre-powercap')
output = Path('/output')
counters = []
for directory, name, watts in [('intel-rapl:0', 'package-0', 40), ('intel-rapl:0:0', 'dram', 10)]:
    domain = root / directory
    domain.mkdir(parents=True)
    (domain / 'name').write_text(name + '\n')
    (domain / 'max_energy_range_uj').write_text('1000000000000\n')
    (domain / 'energy_uj').write_text('1000000000\n')
    counters.append((domain / 'energy_uj', watts))

stop = threading.Event()
errors = []
started = time.monotonic()


def produce():
    try:
        with (output / 'synthetic-counters.jsonl').open('w') as trace:
            while not stop.is_set():
                elapsed = time.monotonic() - started
                values = {}
                for path, watts in counters:
                    value = 1_000_000_000 + int(elapsed * watts * 1_000_000)
                    temporary = path.with_suffix('.tmp')
                    temporary.write_text(str(value) + '\n')
                    temporary.replace(path)
                    values[path.parent.name] = value
                trace.write(json.dumps({'elapsed_seconds': elapsed, 'energy_uj': values}) + '\n')
                trace.flush()
                stop.wait(0.05)
    except Exception as error:
        errors.append(str(error))


producer = threading.Thread(target=produce)
producer.start()
try:
    environment = {**os.environ, 'SCAPHANDRE_POWERCAP_PATH': str(root)}
    subprocess.run(['/usr/local/bin/scaphandre', '--no-header', '--vm', 'json',
                    '--timeout', sys.argv[1], '--step', '1', '--max-top-consumers', '0',
                    '--file', '/output/scaphandre.json'], env=environment,
                   timeout=int(sys.argv[1]) + 30, check=True)
finally:
    stop.set(); producer.join(timeout=5)
    shutil.copytree(root, output / 'powercap', dirs_exist_ok=True)
if errors:
    raise RuntimeError('Synthetic generator failed: ' + '; '.join(errors))
