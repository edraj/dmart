#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Cleaning up dist/, build/, and temporary files..."
rm -rf dist/ build/ *.egg-info dmart info.json

echo "Building CXB..."
CXB_DIR="../cxb"
if [ -d "$CXB_DIR" ]; then
    if [ -f "config.json" ]; then
        cp "config.json" "$CXB_DIR/public/config.json"
    elif [ -f "../config.json" ]; then
        cp "../config.json" "$CXB_DIR/public/config.json"
    elif [ ! -f "$CXB_DIR/public/config.json" ] && [ -f "$CXB_DIR/public/config.sample.json" ]; then
        cp "$CXB_DIR/public/config.sample.json" "$CXB_DIR/public/config.json"
    fi
    pushd "$CXB_DIR"
    yarn install
    yarn build
    popd

    rm -rf cxb
    cp -r "$CXB_DIR/dist/client" cxb
    touch cxb/__init__.py
else
    echo "CXB directory not found at $CXB_DIR"
    exit 1
fi

echo "Installing dependencies..."
uv pip install --upgrade pip build twine
uv pip install .

echo "Creating standalone bundle..."
python3 bundler.py

echo "Building dmart wheel and sdist..."
python3 -m build

rm -rf cxb
ln -s "../cxb/dist/client" cxb

if [ -f "dmart" ]; then
    mv dmart dist/
fi

echo "Uploading to PyPI..."
twine upload --non-interactive dist/*.whl
