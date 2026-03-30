#!/bin/sh

python -m hypercorn main:app --config file:utils/hypercorn_config.py
