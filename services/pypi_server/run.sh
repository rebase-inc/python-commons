#!/bin/bash

# unauthenticated pypi server
/venv/build/bin/pypi-server --overwrite -p 8080 -P .  -a . /wheelhouse
