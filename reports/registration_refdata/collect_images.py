from pathlib import Path
import shutil
import sys
import time
from PIL import Image

root = Path.home() / 'AppData/Roaming/.kodik/sessions/v1/blobs'
candidates = []
for path in root.rglob('*'):
    if not path.is_file() or path.stat().st_mtime < time.time() - 7200:
        continue
    with path.open('rb') as stream:
        if stream.read(8) != b'\x89PNG\r\n\x1a\n':
            continue
    candidates.append(path)
source = max(candidates, key=lambda path: path.stat().st_mtime)
target = Path(__file__).parent / 'screenshots' / sys.argv[1]
shutil.copyfile(source, target)
print(target, Image.open(target).size)
