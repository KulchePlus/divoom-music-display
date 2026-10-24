"""Check app, Windows resource and release tag versions."""
import os
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from version import VERSION
resource = (root/'version_info.txt').read_text(encoding='utf-8')
assert f"filevers=({', '.join(VERSION.split('.'))}, 0)" in resource
assert f"prodvers=({', '.join(VERSION.split('.'))}, 0)" in resource
assert f"StringStruct('FileVersion', '{VERSION}')" in resource
assert f"StringStruct('ProductVersion', '{VERSION}')" in resource
if os.environ.get('GITHUB_REF_TYPE') == 'tag':
    assert os.environ['GITHUB_REF_NAME'] == 'v'+VERSION, 'Release tag must match version.py'
print('Version metadata OK: v'+VERSION)
