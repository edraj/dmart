#!/bin/sh

# Python: use ipdb instead of pdb
export PYTHONBREAKPOINT=ipdb.set_trace
export PATH=$HOME/.local/bin:$PATH

BASEDIR=$(dirname "$(realpath $0)")
export BACKEND_ENV="${BACKEND_ENV:-${BASEDIR}/config.env}"
LISTENING_PORT=$(grep -i '^LISTENING_PORT' $BACKEND_ENV | sed 's/^[^=]* *= *//g' | tr -d '"' | tr -d "'")
LISTENING_HOST=$(grep -i '^LISTENING_HOST' $BACKEND_ENV | sed 's/^[^=]* *= *//g' | tr -d '"' | tr -d "'")

cd $BASEDIR
PROCS=$(nproc --all)
# PROCS=1
hypercorn --log-config json_log.ini -w ${PROCS}  --backlog 200 -b $LISTENING_HOST':'$LISTENING_PORT -k 'asyncio' main:app
