#!/usr/bin/env -S BACKEND_ENV=config.env python3
import PyInstaller.__main__

PyInstaller.__main__.run([
    'dmart.py',
    '--name=dmart',
    '--onefile',
    '--runtime-tmpdir=.',
    '--distpath=.',
    '--paths=/home/splimter/projects/open-source/dmart/samples/spaces',
    '--add-data=./config.env:.',
    '--noconfirm',
    '--collect-submodules=concurrent_log_handler',
    '--clean',
])
