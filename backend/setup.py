import os
from setuptools import setup, find_packages

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def parse_requirements(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Requirements file not found: {path}")
    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

install_requires = parse_requirements('requirements/core.txt')
extra_requires = parse_requirements('requirements/extra.txt')
plugins_requires = parse_requirements('requirements/plugins.txt')

sub_packages = find_packages(exclude=['tests', 'pytests', 'loadtest'])

packages = ['dmart'] + [f'dmart.{pkg}' for pkg in sub_packages]

package_dir = {'dmart': '.'}

setup(
    name="dmart",
    version="1.4.36",
    packages=packages,
    package_dir=package_dir,
    package_data={
        'dmart': [
            '*.json', '*.toml', '*.sh', '*.sample', 'alembic.ini',
            'dmart.py', 'main.py', 'sync.py', 'bundler.py', 'migrate.py', 
            'password_gen.py', 'get_settings.py', 'data_generator.py', 
            'schema_modulate.py', 'schema_migration.py', 'set_admin_passwd.py', 
            'run_notification_campaign.py', 'scheduled_notification_handler.py', 
            'websocket.py', 'test_utils.py', 'conftest.py'
        ],
        'dmart.cxb': ['**/*'],
        'dmart.languages': ['*.json'],
        'dmart.config': ['*.json'],
        'dmart.plugins': ['**/*.json', '**/*.schema', '**/*.conf'],
        'dmart.utils': ['templates/*.j2'],
        'dmart.alembic': ['**/*'],
    },
    install_requires=install_requires,
    extras_require={
        "extra": extra_requires,
        "plugins": plugins_requires,
        "all": extra_requires + plugins_requires,
    },
    entry_points={
        "console_scripts": [
            "dmart=dmart.dmart:main",
        ],
    },
    include_package_data=True,
    python_requires=">=3.11",
)
