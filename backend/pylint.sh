#!/bin/bash

echo "Pyright ..."
python -m pyright .
echo "Ruff ..."
python -m ruff check --exclude pytests .
echo "Mypy ..."
python -m mypy --install-types --explicit-package-bases --warn-return-any --check-untyped-defs --exclude loadtest --exclude pytests .
