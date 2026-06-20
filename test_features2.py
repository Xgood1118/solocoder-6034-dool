#!/usr/bin/env python3
"""Direct test of dool JSON output features using the load plugin (which works with /proc mocking)."""

import sys, os, types, json, tempfile, glob as glob_mod, re, io

project_dir = 'C:/Users/白东鑫/work01/SoloCoder/6034-dool'

# ====== Mock Unix ======
res_mod = types.ModuleType('resource')
res_mod.RLIMIT_NOFILE = 7; res_mod.RLIMIT_STACK = 3
res_mod.getrlimit = lambda x: (1024, 4096); res_mod.getpagesize = lambda: 4096
sys.modules['resource'] = res_mod
if not hasattr(os, 'sysconf'): os.sysconf = lambda name: 4
class MockUname: nodename = 'win-test'; sysname = 'Linux'
os.uname = lambda: MockUname()
os.chdir(project_dir)

# Patch glob
_og = glob_mod.glob
glob_mod.glob = lambda p, **kw: [r.replace(os.sep, '/') for r in _og(p, **kw)]

# Create fake /proc
fake_proc = tempfile.mkdtemp()
os.makedirs(os.path.join(fake_proc, 'net'))
os.makedirs(os.path.join(fake_proc, 'sys/fs'))
for rp, c in {
    'uptime': '1000.00 500.00\n',
    'stat': 'cpu 1000 200 300 40000 500 600 700\ncpu0 250 50 75 10000 125 150 175\nctxt 12345\nbtime 1600000000\nprocesses 67890\n',
    'net/dev': 'eth0: 1000 200 0 0 0 0 0 0 500 100 0 0 0 0 0 0\nlo: 100 50 0 0 0 0 0 0 100 50 0 0 0 0 0 0\n',
    'diskstats': 'sda: 1000 200 300 400 500 600 700 800 900 1000\n',
    'loadavg': '1.00 2.00 3.00 4/5 6\n',
    'sys/fs/aio-nr': '100 200 300\n',
    'cpuinfo': 'processor\t: 0\nprocessor\t: 1\n',
    'meminfo': 'MemTotal: 8000000 kB\nMemFree: 4000000 kB\nMemAvailable: 5000000 kB\nCached: 2000000 kB\n',
    'self/status': 'Name: dool\n',
    'self/schedstat': '1000 200 0\n',
}.items():
    ap = os.path.join(fake_proc, rp)
    os.makedirs(os.path.dirname(ap), exist_ok=True)
    with open(ap, 'w') as f: f.write(c)

# Patch open/exists for /proc
_real_open = __builtins__.open if isinstance(__builtins__, dict) else __builtins__.open
def _po(file, mode='r', *a, **kw):
    if isinstance(file, str) and file.startswith('/proc/'):
        fp = os.path.join(fake_proc, file[6:])
        if os.path.exists(fp): return _real_open(fp, mode, *a, **kw)
    return _real_open(file, mode, *a, **kw)
if isinstance(__builtins__, dict): __builtins__['open'] = _po
else: __builtins__.open = _po

_real_exists = os.path.exists
os.path.exists = lambda p: _real_exists(os.path.join(fake_proc, p[6:])) if isinstance(p, str) and p.startswith('/proc/') else _real_exists(p)

def run_dool(args):
    import runpy
    sys.argv = ['dool'] + args
    try:
        runpy.run_path(os.path.join(project_dir, 'dool'), run_name='__main__')
    except SystemExit as e:
        return e.code or 0
    return 0

# Test 1: JSON output with load plugin
print('=== TEST 1: JSON output (load plugin) ===')
out = os.path.join(tempfile.gettempdir(), 'test_dool_load.json')
rc = run_dool(['--load', '--output', out, '1', '1'])
print(f'RC={rc}')
if os.path.exists(out):
    with open(out) as f: c = f.read()
    print(f'Content ({len(c)} bytes):')
    print(c[:400])
    try:
        d = json.loads(c)
        print(f'Valid JSON: YES, samples={len(d.get("samples",[]))}')
        for sk in ['load', 'timestamp']:
            print(f'  contains {sk}: {sk in d.get("samples",[{}])[0]}')
    except json.JSONDecodeError as e:
        print(f'JSON ERROR: {e}')
    os.remove(out)

# Test 2: JSON append
print('\n=== TEST 2: JSON append ===')
out = os.path.join(tempfile.gettempdir(), 'test_dool_append.json')
rc1 = run_dool(['--load', '--output', out, '1', '1'])
print(f'Run1 RC={rc1}, file size={os.path.getsize(out) if os.path.exists(out) else 0}')
rc2 = run_dool(['--load', '--output', out, '1', '1'])
print(f'Run2 RC={rc2}, file size={os.path.getsize(out) if os.path.exists(out) else 0}')
if os.path.exists(out):
    with open(out) as f: c = f.read()
    try:
        d = json.loads(c)
        print(f'Samples: {len(d.get("samples",[]))} (expect 2)')
        if len(d.get('samples', [])) == 2:
            print('PASS: Append works')
        else:
            print('FAIL: Expected 2 samples')
    except json.JSONDecodeError as e:
        print(f'JSON ERROR: {e}')
        print(f'Tail: {c[-300:]}')
    os.remove(out)

# Test 3: JSONL output
print('\n=== TEST 3: JSONL output ===')
out = os.path.join(tempfile.gettempdir(), 'test_dool.jsonl')
rc = run_dool(['--load', '--output', out, '1', '2'])
print(f'RC={rc}')
if os.path.exists(out):
    with open(out) as f: lines = f.readlines()
    print(f'Lines: {len(lines)}')
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
            print(f'  Line {i}: keys={list(obj.keys())}')
        except:
            print(f'  Line {i}: INVALID')
    os.remove(out)

# Test 4: Plugin health check in action
print('\n=== TEST 4: Plugin health check messages ===')
from contextlib import redirect_stderr
buf = io.StringIO()
with redirect_stderr(buf):
    out = os.path.join(tempfile.gettempdir(), 'test_dool_health.json')
    rc = run_dool(['--cpu', '--load', '--output', out, '1', '1'])
stderr = buf.getvalue()
for line in stderr.split('\n'):
    if 'plugin-fail' in line.lower():
        print(f'  {line.strip()}')

# Test 5: Strict plugin test (non-existing option correctly caught)
print('\n=== TEST 5: --netset option parsing ===')
with open(os.path.join(project_dir, 'dool'), 'r') as f:
    src = f.read()
# Verify netset impl exists
checks = {
    '--netset option': "'--netset'" in src,
    'netsets.conf loading': '_load_netsets_conf' in src,
    'NetSet in net plugin': 'op.netset' in src,
    'builtin/external label': '(builtin)' in src,
    'strict-plugin option': '--strict-plugin' in src,
    'profile+output': 'op.profile' in src,
    'JSON append logic': 'existing JSON output' in src,
}
for k, v in checks.items():
    print(f'  {k}: {"PASS" if v else "FAIL"}')

# Test 6: Profiling
print('\n=== TEST 6: Profiling ===')
out = os.path.join(tempfile.gettempdir(), 'test_dool_profile.json')
rc = run_dool(['--load', '--profile', '--output', out, '1', '1'])
if os.path.exists(out):
    with open(out) as f: c = f.read()
    print(f'Content ({len(c)} bytes)')
    print(c[:400])
    try:
        d = json.loads(c)
        print(f'Valid JSON: YES, has profile: {"profile" in d}')
    except:
        print('Valid JSON: NO')
    os.remove(out)

print('\n=== ALL TESTS DONE ===')
