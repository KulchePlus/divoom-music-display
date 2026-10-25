"""Package only the portable app and its documentation."""
import hashlib
import sys
import zipfile
import shutil
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from version import VERSION
out = root/'release'
out.mkdir(exist_ok=True)
archive = out/'Divoom.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
    for file in ('Divoom.exe', 'README.md', 'CHANGELOG.md', 'THIRD_PARTY_NOTICES.md'):
        bundle.write(root/file, file)
checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
legacy_archive = out/f'Divoom-v{VERSION}-windows-x64.zip'
shutil.copyfile(archive, legacy_archive)
(out/'SHA256SUMS.txt').write_text(
    f'{checksum}  {archive.name}\n{checksum}  {legacy_archive.name}\n', encoding='ascii')
print(archive.name)
print(checksum)
