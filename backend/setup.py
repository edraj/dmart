import os
from setuptools import setup, find_packages

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def parse_requirements(filename):
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

install_requires = parse_requirements('requirements/core.txt')
extra_requires = parse_requirements('requirements/extra.txt')
plugins_requires = parse_requirements('requirements/plugins.txt')

setup(
    name="dmart",
    version="1.4.0",
    packages=find_packages(),
    py_modules=["dmart", "main", "sync", "bundler", "migrate", "password_gen", "get_settings", "data_generator", "schema_modulate", "schema_migration", "set_admin_passwd", "run_notification_campaign", "scheduled_notification_handler", "websocket"],
    install_requires=install_requires,
    extras_require={
        "extra": extra_requires,
        "plugins": plugins_requires,
        "all": extra_requires + plugins_requires,
    },
    entry_points={
        "console_scripts": [
            "dmart=dmart:main",
        ],
    },
    include_package_data=True,
    python_requires=">=3.11",
)
