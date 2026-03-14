#!/bin/bash

declare -i RESULT=0
export PYRIGHT_PYTHON_FORCE_VERSION=latest
echo "Pyright ..."
python -m pyright .
RESULT+=$?
echo "Ruff ..."
python -m ruff check --exclude pytests --exclude alembic .
RESULT+=$?
echo "Mypy ..."
python -m mypy --explicit-package-bases --warn-return-any --check-untyped-defs --exclude loadtest --exclude pytests --exclude alembic .
RESULT+=$?

echo "Result : $RESULT"
exit $RESULT
