#!/usr/bin/env python3
"""Test wrapper for dool on Windows - mocks all Unix-specific dependencies."""

import sys
import os

# Add the project dir to path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# --- Mock Unix-specific modules and functions ---
import types

# Mock resource module
resource_mod = types.ModuleType('resource')
resource_mod.RLIMIT_NOFILE = 7
resource_mod.RLIMIT_STACK = 3
resource_mod.getrlimit = lambda x: (1024, 4096)
resource_mod.getpagesize = lambda: 4096
sys.modules['resource'] = resource_mod

# Mock os.sysconf
if not hasattr(os, 'sysconf'):
    os.sysconf = lambda name: 4

# Mock os.uname
class MockUname:
    def __init__(self):
        self.nodename = 'win-test'
        self.sysname = 'Linux'
os.uname = lambda: MockUname()

# Patch glob to normalize paths
import glob as _glob_mod
_original_glob = _glob_mod.glob
def _patched_glob(pathname, **kwargs):
    results = _original_glob(pathname, **kwargs)
    return [r.replace(os.sep, '/') for r in results]
_glob_mod.glob = _patched_glob

# Create fake /proc files in a temp dir
import tempfile, shutil
fake_proc = os.path.join(tempfile.gettempdir(), 'dool_fakeproc')
if os.path.exists(fake_proc):
    shutil.rmtree(fake_proc)
os.makedirs(os.path.join(fake_proc, 'net'))
os.makedirs(os.path.join(fake_proc, 'sys/fs'))

# Write fake files
files = {
    'uptime': '1000.00 500.00\n',
    'stat': (
        'cpu  1000 200 300 40000 500 600 700\n'
        'cpu0 250 50 75 10000 125 150 175\n'
        'cpu1 250 50 75 10000 125 150 175\n'
        'intr 0 1 2 3 4 5 6 7 8 9 10\n'
        'ctxt 12345\n'
        'btime 1600000000\n'
        'processes 67890\n'
    ),
    'net/dev': 'eth0: 1000 200 0 0 0 0 0 0 500 100 0 0 0 0 0 0\n',
    'diskstats': 'sda: 1000 200 300 400 500 600 700 800 900 1000\n',
    'loadavg': '1.00 2.00 3.00 4/5 6\n',
    'sys/fs/aio-nr': '100 200 300\n',
}
for relpath, content in files.items():
    abspath = os.path.join(fake_proc, relpath)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    with open(abspath, 'w') as f:
        f.write(content)

# Check if dool looks for /proc/cpuinfo too
with open(os.path.join(fake_proc, 'cpuinfo'), 'w') as f:
    f.write('processor\t: 0\n')
    f.write('processor\t: 1\n')
    f.write('processor\t: 2\n')
    f.write('processor\t: 3\n')

# Override open() for /proc/ paths
_real_open = __builtins__.open if isinstance(__builtins__, dict) else __builtins__.open

def _patched_open(file, mode='r', *args, **kwargs):
    # Redirect /proc/ paths to fake proc
    if isinstance(file, str) and file.startswith('/proc/'):
        fake_path = os.path.join(fake_proc, file[6:])  # strip '/proc/'
        if os.path.exists(fake_path):
            return _real_open(fake_path, mode, *args, **kwargs)
    return _real_open(file, mode, *args, **kwargs)

if isinstance(__builtins__, dict):
    __builtins__['open'] = _patched_open
else:
    __builtins__.open = _patched_open

# Also patch os.path.exists for /proc paths
_real_exists = os.path.exists
def _patched_exists(path):
    if isinstance(path, str) and path.startswith('/proc/'):
        fake_path = os.path.join(fake_proc, path[6:])
        if os.path.exists(fake_path):
            return True
    return _real_exists(path)
os.path.exists = _patched_exists

# Run dool
import runpy
sys.argv = sys.argv[1:] if sys.argv[0].endswith('run_wrapper.py') else sys.argv
try:
    runpy.run_path(os.path.join(project_dir, 'dool'), run_name='__main__')
except SystemExit as e:
    sys.exit(e.code if e.code else 0)
except KeyboardInterrupt:
    sys.exit(0)
