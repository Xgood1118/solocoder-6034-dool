#!/usr/bin/env python3
"""Test wrapper for dool on Windows - mocks all Unix-specific dependencies."""

import sys
import os
import types
import re
import glob

# --- Mock Unix-specific modules and functions ---

# Mock resource module
resource_mod = types.ModuleType('resource')
resource_mod.RLIMIT_NOFILE = 7
resource_mod.RLIMIT_STACK = 3
resource_mod.getrlimit = lambda x: (1024, 4096)
resource_mod.getpagesize = lambda: 4096
sys.modules['resource'] = resource_mod

# Mock os.sysconf
import os as _real_os
if not hasattr(_real_os, 'sysconf'):
    _real_os.sysconf = lambda name: 4  # 4 CPUs

# Mock os.uname
if not hasattr(_real_os, 'uname'):
    import platform
    _real_os.uname = lambda: platform.uname()

# Mock os.uname result to have nodename
class MockUname:
    def __init__(self):
        self.nodename = 'win-test'
        self.sysname = 'Linux'  # trick dool into thinking it's Linux
if hasattr(_real_os, 'uname'):
    _orig_uname = _real_os.uname
    _real_os.uname = lambda: MockUname()

# Patch glob.glob to normalize paths
_original_glob = glob.glob
def _patched_glob(pathname, **kwargs):
    results = _original_glob(pathname, **kwargs)
    return [r.replace(_real_os.sep, '/') for r in results]
glob.glob = _patched_glob

# Read /proc/stat substitute for CPU info
# Create a fake /proc/stat
import tempfile
proc_dir = tempfile.mkdtemp()
stat_path = os.path.join(proc_dir, 'stat')
with open(stat_path, 'w') as f:
    f.write("cpu  1000 200 300 40000 500 600 700\n")
    f.write("cpu0 250 50 75 10000 125 150 175\n")
    f.write("cpu1 250 50 75 10000 125 150 175\n")
    f.write("cpu2 250 50 75 10000 125 150 175\n")
    f.write("cpu3 250 50 75 10000 125 150 175\n")
    f.write("intr 0 1 2 3 4 5 6 7 8 9 10\n")
    f.write("ctxt 12345\n")
    f.write("btime 1600000000\n")
    f.write("processes 67890\n")
    f.write("procs_running 2\n")
    f.write("procs_blocked 0\n")

# Override /proc/stat reading - patch open for specific paths
_original_open = _real_os.open if hasattr(_real_os, 'open') else None

# Simple approach: set environment to use a fake proc dir
os.environ['DOOL_PROC'] = proc_dir

sys.argv = sys.argv[1:] if len(sys.argv) > 1 and sys.argv[0].endswith('run_dool_test.py') else sys.argv

import runpy
try:
    runpy.run_path(os.path.join(os.path.dirname(__file__), 'dool'), run_name='__main__')
except SystemExit as e:
    sys.exit(e.code if e.code else 0)
except KeyboardInterrupt:
    sys.exit(0)
