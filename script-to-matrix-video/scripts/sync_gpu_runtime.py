"""Synchronize portable GPU launchers into saved template folders (maintenance only)."""
import argparse
import json
from pathlib import Path
import re
import shutil

def sync(root):
    root = Path(root).resolve()
    count = 0
    for package in sorted((root/'assets/templates').glob('*/package.json')):
        data = json.loads(package.read_text(encoding='utf-8-sig'))
        versions = re.findall(r'hyperframes@(0\.8\.\d+)', json.dumps(data))
        if not versions:
            raise ValueError('No saved CLI version: ' + str(package))
        version = versions[0]
        folder = package.parent
        shutil.copy2(root/'scripts/gpu_runtime.py', folder/'gpu_runtime.py')
        command = f'python gpu_runtime.py --version {version} -- --sdr --fps 30 --quality high --workers 2'
        if folder.name == 'bilingual-stagger-salon':
            for name in ('render_gpu_hdr.py', 'hyperframes_hdr_patch.py'):
                shutil.copy2(root/'scripts'/name, folder/name)
            data['scripts']['render'] = 'python render_gpu_hdr.py .'
            data['scripts']['render:sdr'] = command
        else:
            data['scripts']['render'] = command
        package.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        count += 1
    return count

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('skill', nargs='?', default=str(Path(__file__).resolve().parents[1]))
    print('Synchronized template families:', sync(p.parse_args().skill))
