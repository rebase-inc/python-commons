#!/bin/bash

# unauthenticated pypi server
/venv/build/bin/pypi-server -p 8080 -P .  -a . /wheelhouse
