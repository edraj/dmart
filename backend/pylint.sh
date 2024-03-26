#!/bin/bash

echo "Pyright ..."
python -m pyright
echo "Ruff ..."
python -m ruff check .
echo "Mypy ..."
python -m mypy --explicit-package-bases --warn-return-any .

