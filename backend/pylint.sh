#!/bin/bash

echo "Pyright ..."
pyright
echo "Ruff ..."
ruff check .
echo "Mypy ..."
mypy --explicit-package-bases --warn-return-any .

