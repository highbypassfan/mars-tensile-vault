"""Launch scene_tools.py in an isolated background Blender process."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__, epilog='Remaining arguments go to scene_tools.py; see docs/SCENE-TOOLS.md')
    parser.add_argument('--blender', help='Blender executable; alternatively set BLENDER_EXE')
    parser.add_argument('--blend', default=str(root / 'mars-tensile-vault.blend'))
    args, rest = parser.parse_known_args()
    executable = args.blender or os.environ.get('BLENDER_EXE') or shutil.which('blender')
    if not executable:
        candidates = sorted(Path('C:/Program Files/Blender Foundation').glob('Blender */blender.exe'))
        executable = str(candidates[-1]) if candidates else None
    if not executable:
        parser.error('Blender not found; supply --blender or BLENDER_EXE')
    if not Path(args.blend).is_file():
        parser.error(f'Blend not found: {args.blend}')
    command = [executable, '--factory-startup', '--background', '--disable-autoexec', args.blend,
               '--python-exit-code', '1', '--python', str(root / 'tools/scene_tools.py'), '--', *rest]
    return subprocess.run(command, check=False).returncode


if __name__ == '__main__':
    sys.exit(main())
