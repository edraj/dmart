#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Cleaning up dist/, build/, and temporary files..."
rm -rf dist/ build/ *.egg-info dmart info.json

echo "Installing dependencies..."
python3 -m pip install --upgrade pip build twine
python3 -m pip install .
if [ -d "requirements" ]; then
    for req in requirements/*.txt; do
        if [ -f "$req" ] && [[ "$req" != *"test.txt" ]]; then
            python3 -m pip install -r "$req"
        fi
    done
fi

echo "Creating standalone bundle..."
python3 bundler.py

echo "Building dmart wheel and sdist..."
python3 -m build

if [ -f "dmart" ]; then
    mv dmart dist/
fi

echo "Uploading to PyPI..."
twine upload --non-interactive dist/*.whl
