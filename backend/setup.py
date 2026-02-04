import os
import shutil
from setuptools import setup, find_packages

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

cli_src = os.path.join(BASE_DIR, '..', 'cli', 'cli.py')
if os.path.exists(cli_src):
    shutil.copy(cli_src, os.path.join(BASE_DIR, 'cli.py'))

config_src = os.path.join(BASE_DIR, '..', 'cli', 'config.ini.sample')
if os.path.exists(config_src):
    shutil.copy(config_src, os.path.join(BASE_DIR, 'config.ini.sample'))

sample_src = os.path.join(BASE_DIR, '..', 'sample')
sample_dst = os.path.join(BASE_DIR, 'sample')
if os.path.exists(sample_src):
    if os.path.exists(sample_dst):
        shutil.rmtree(sample_dst)
    shutil.copytree(sample_src, sample_dst)

def parse_requirements(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Requirements file not found: {path}")
    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

def get_sample_files():
    files = []
    sample_dir = os.path.join(BASE_DIR, 'sample')
    if not os.path.exists(sample_dir):
        return []
    for root, _, filenames in os.walk(sample_dir):
        for filename in filenames:
            rel_dir = os.path.relpath(root, BASE_DIR)
            files.append(os.path.join(rel_dir, filename))
    return files

install_requires = parse_requirements('requirements/core.txt')
cli_requires = parse_requirements('requirements/cli.txt')

install_requires = install_requires + cli_requires
install_requires.append('alembic')

sub_packages = find_packages(exclude=['tests', 'pytests', 'loadtest'])

packages = ['dmart'] + [f'dmart.{pkg}' for pkg in sub_packages]

package_dir = {'dmart': '.'}

setup(
    name="dmart",
    version="1.4.41-47",
    packages=packages,
    package_dir=package_dir,
    package_data={
        'dmart': [
            '*.json', '*.toml', '*.sh', '*.sample', 'alembic.ini',
            'dmart.py', 'main.py', 'sync.py', 'bundler.py', 'migrate.py', 
            'password_gen.py', 'get_settings.py', 'data_generator.py', 
            'schema_modulate.py', 'schema_migration.py', 'set_admin_passwd.py', 
            'run_notification_campaign.py', 'scheduled_notification_handler.py', 
            'websocket.py', 'test_utils.py', 'conftest.py', 'cli.py'
        ] + get_sample_files(),
        'dmart.cxb': ['**/*'],
        'dmart.languages': ['*.json'],
        'dmart.config': ['*.json'],
        'dmart.plugins': ['**/*.json', '**/*.schema', '**/*.conf'],
        'dmart.utils': ['templates/*.j2'],
        'dmart.alembic': ['**/*'],
    },
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "dmart=dmart.dmart:main",
        ],
    },
    include_package_data=True,
    python_requires=">=3.11",
)
