#!/usr/bin/env -S BACKEND_ENV=config.env python3
import json
import subprocess
import PyInstaller.__main__
import os

branch_cmd = "git rev-parse --abbrev-ref HEAD"
result, _ = subprocess.Popen(branch_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
branch = None if result is None or len(result) == 0 else result.decode().strip()

version_cmd = "git rev-parse --short HEAD"
result, _ = subprocess.Popen(version_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
version = None if result is None or len(result) == 0 else result.decode().strip()

tag_cmd = "git describe --tags"
result, _ = subprocess.Popen(tag_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
tag = None if result is None or len(result) == 0 else result.decode().strip()

version_date_cmd = "git show --pretty=format:'%ad'"
result, _ = subprocess.Popen(version_date_cmd.split(" "), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
version_date = None if result is None or len(result) == 0 else result.decode().split("\n")[0]

info = {
    "branch": branch,
    "version": version,
    "tag": tag,
    "version_date": version_date
}

json.dump(info, open('info.json', 'w'))

args = [
    'dmart.py',
    '--name=dmart',
    '--onefile',
    '--runtime-tmpdir=.',
    '--distpath=.',
    '--add-data=./info.json:.',
    '--noconfirm',
    '--collect-submodules=concurrent_log_handler',
    '--collect-submodules=pythonjsonlogger',
    '--clean',
]

cxb_path = 'cxb'
if not os.path.isdir(cxb_path):
    cxb_path = '../cxb/dist/client'

if os.path.isdir(cxb_path):
    args.append(f'--add-data={cxb_path}:cxb')

PyInstaller.__main__.run(args)
