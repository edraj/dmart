#!/bin/sh
$HOME/venv/bin/python3 -m hypercorn main:app --config file:utils/hypercorn_config.py
