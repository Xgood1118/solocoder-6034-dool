#!/usr/bin/env python3
"""Test dool PROMPT features on Windows with mocked /proc."""

import sys, os, types, glob as glob_mod, json, tempfile, shutil

project_dir = 'C:/Users/白东鑫/work01/SoloCoder/6034-dool'
os.chdir(project_dir)

# ====== Mock Unix modules ======
res_mod = types.ModuleType('resource')
res_mod.RLIMIT_NOFILE = 7; res_mod.RLIMIT_STACK = 3
res_mod.getrlimit = lambda x: (1024, 4096); res_mod.getpagesize = lambda: 4096
sys.modules['resource'] = res_mod

if not hasattr(os, 'sysconf'): os.sysconf = lambda name: 4

class MockUname:
    nodename = 'win-test'; sysname = 'Linux'
os.uname = lambda: MockUname()

# ====== Patch glob ======
_orig_glob = glob_mod.glob
def _patched_glob(pathname, **kwargs):
    return [r.replace(os.sep, '/') for r in _orig_glob(pathname, **kwargs)]
glob_mod.glob = _patched_glob

# ====== Create fake /proc ======
fake_proc = os.path.join(tempfile.gettempdir(), 'dool_fakeproc_' + str(os.getpid()))
if os.path.exists(fake_proc): shutil.rmtree(fake_proc)
os.makedirs(os.path.join(fake_proc, 'net'))
os.makedirs(os.path.join(fake_proc, 'sys/fs'))
for relpath, content in {
    'uptime': '1000.00 500.00\n',
    'stat': 'cpu  1000 200 300 40000 500 600 700\ncpu0 250 50 75 10000 125 150 175\nbtime 1600000000\nprocesses 67890\nctxt 12345\n',
    'net/dev': 'eth0: 1000 200 0 0 0 0 0 0 500 100 0 0 0 0 0 0\nlo: 100 50 0 0 0 0 0 0 100 50 0 0 0 0 0 0\n',
    'diskstats': 'sda: 1000 200 300 400 500 600 700 800 900 1000\n',
    'loadavg': '1.00 2.00 3.00 4/5 6\n',
    'sys/fs/aio-nr': '100 200 300\n',
    'cpuinfo': 'processor\t: 0\nprocessor\t: 1\nprocessor\t: 2\nprocessor\t: 3\n',
    'meminfo': 'MemTotal:       8000000 kB\nMemFree:        4000000 kB\nMemAvailable:   5000000 kB\nCached:         2000000 kB\n',
    'self/status': 'Name:   dool\n',
}.items():
    ap = os.path.join(fake_proc, relpath)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, 'w') as f: f.write(content)

# ====== Redirect /proc/ paths ======
_real_open = __builtins__.open if isinstance(__builtins__, dict) else __builtins__.open
def _patch_open(file, mode='r', *args, **kwargs):
    if isinstance(file, str) and file.startswith('/proc/'):
        fp = os.path.join(fake_proc, file[6:])
        if os.path.exists(fp): return _real_open(fp, mode, *args, **kwargs)
    return _real_open(file, mode, *args, **kwargs)
if isinstance(__builtins__, dict): __builtins__['open'] = _patch_open
else: __builtins__.open = _patch_open

_real_exists = os.path.exists
def _patch_exists(path):
    if isinstance(path, str) and path.startswith('/proc/'):
        fp = os.path.join(fake_proc, path[6:])
        if os.path.exists(fp): return True
    return _real_exists(path)
os.path.exists = _patch_exists

# ====== Helper to run dool ======
def run_dool(args):
    import runpy
    sys.argv = ['dool'] + args
    try:
        runpy.run_path(os.path.join(project_dir, 'dool'), run_name='__main__')
    except SystemExit as e:
        return e.code

# ==================================================================
# TEST 1: JSON output basic
# ==================================================================
print('=' * 60)
print('TEST 1: JSON output basic')
out1 = os.path.join(tempfile.gettempdir(), 'dool_test1.json')
rc = run_dool(['--epoch', '--output', out1, '1', '1'])
print(f'RC={rc}')
if os.path.exists(out1):
    with open(out1) as f: content = f.read()
    try:
        data = json.loads(content)
        print(f'VALID JSON: samples={len(data.get("samples", []))}')
        if data.get('samples'):
            s0 = data['samples'][0]
            print(f'Sample keys: {list(s0.keys())}')
            if 'timestamp' in s0: print(f'  has timestamp: {s0["timestamp"]}')
    except json.JSONDecodeError as e:
        print(f'INVALID JSON: {e}')
        print(f'Content: {content[:300]}')
    os.remove(out1)

# ==================================================================
# TEST 2: JSONL output
# ==================================================================
print('=' * 60)
print('TEST 2: JSONL output')
out2 = os.path.join(tempfile.gettempdir(), 'dool_test2.jsonl')
rc = run_dool(['--epoch', '--output', out2, '1', '2'])
print(f'RC={rc}')
if os.path.exists(out2):
    with open(out2) as f: lines = f.readlines()
    print(f'Lines: {len(lines)}')
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
            has_ts = 'timestamp' in obj; has_epoch = 'epoch' in obj
            print(f'  line {i}: keys={list(obj.keys())} ts={has_ts} epoch={has_epoch}')
        except Exception as e:
            print(f'  line {i}: INVALID: {e}')
    os.remove(out2)

# ==================================================================
# TEST 3: JSON append (test R1 JSON append fix)
# ==================================================================
print('=' * 60)
print('TEST 3: JSON append (R1 bug fix)')
out3 = os.path.join(tempfile.gettempdir(), 'dool_test3.json')

# First run - should create file
rc1 = run_dool(['--epoch', '--output', out3, '1', '1'])
print(f'Run 1 RC={rc1}')

# Second run - should append to existing file
rc2 = run_dool(['--epoch', '--output', out3, '1', '1'])
print(f'Run 2 RC={rc2}')

if os.path.exists(out3):
    with open(out3) as f: content = f.read()
    try:
        data = json.loads(content)
        samples = data.get('samples', [])
        print(f'Samples: {len(samples)} (expected 2)')
        if len(samples) == 2:
            print('PASS: Append works correctly')
        else:
            print(f'FAIL: Expected 2 samples, got {len(samples)}')
    except json.JSONDecodeError as e:
        print(f'POSSIBLE ISSUE: {e}')
        last_200 = content[-200:]
        print(f'Tail: {repr(last_200)}')
    os.remove(out3)

# ==================================================================
# TEST 4: Plugin Health Check - plugin-fail output
# ==================================================================
print('=' * 60)
print('TEST 4: Plugin Health Check')
import io
from contextlib import redirect_stderr
buf = io.StringIO()
with redirect_stderr(buf):
    rc = run_dool(['--cpu', '--output', os.path.join(tempfile.gettempdir(), 'dool_test4.json'), '1', '1'])
stderr_text = buf.getvalue()
print(f'Stderr contains plugin-fail: {"[plugin-fail]" in stderr_text}')
if '[plugin-fail]' in stderr_text:
    for line in stderr_text.split('\n'):
        if '[plugin-fail]' in line:
            print(f'  {line}')

# ==================================================================
# TEST 5: Strict plugin (should fail on plugin health check)
# ==================================================================
print('=' * 60)
print('TEST 5: --strict-plugin (should exit 2 if plugin fails)')
buf = io.StringIO()
with redirect_stderr(buf):
    rc = run_dool(['--nonexistent-plugin', '--strict-plugin', '--output', os.path.join(tempfile.gettempdir(), 'dool_test5.json'), '1', '1'])
print(f'Exit code: {rc}')
print(f'PASS (exits on failure): {rc == 8}')

# ==================================================================
# TEST 6: NetSet functionality (code analysis)
# ==================================================================
print('=' * 60)
print('TEST 6: NetSet (code analysis)')

# Read dool source to verify netset
with open(os.path.join(project_dir, 'dool'), 'r') as f:
    source = f.read()

# Check netset parsing
has_netset_opt = "'--netset'" in source
has_netset_conf = '_load_netsets_conf' in source
has_netset_vars = 'self.netset' in source
print(f'  --netset option: {has_netset_opt}')
print(f'  netsets.conf loading: {has_netset_conf}')
print(f'  netset dict: {has_netset_vars}')

# Verify NetSet is used in dool_net.vars()
has_netset_in_net = 'op.netset' in source
print(f'  NetSet used in net plugin: {has_netset_in_net}')

# ==================================================================
# TEST 7: Plugin source differentiation (builtin vs external)
# ==================================================================
print('=' * 60)
print('TEST 7: Plugin source label in health check')
has_builtin_label = '(builtin)' in source
print(f'  Has builtin label: {has_builtin_label}')

# ==================================================================
# TEST 8: Profiling with JSON output
# ==================================================================
print('=' * 60)
print('TEST 8: Profiling with JSON output')
out8 = os.path.join(tempfile.gettempdir(), 'dool_test8.json')
rc = run_dool(['--epoch', '--profile', '--output', out8, '1', '1'])
print(f'RC={rc}')
if os.path.exists(out8):
    with open(out8) as f: content = f.read()
    try:
        data = json.loads(content)
        has_profile = 'profile' in data
        has_samples = 'samples' in data
        print(f'  Has samples: {has_samples}')
        print(f'  Has profile: {has_profile}')
        if has_profile:
            print(f'  Profile keys: {list(data["profile"].keys())}')
        if has_samples:
            s0 = data['samples'][0]
            has_profile_in_sample = '_profile' in s0
            print(f'  Has _profile in sample: {has_profile_in_sample}')
    except json.JSONDecodeError as e:
        print(f'  JSON error: {e}')
    os.remove(out8)

print('=' * 60)
print('ALL TESTS DONE')
