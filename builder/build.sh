#!/bin/sh
echo 'Starting a new build...'
sleep 5
touch ~/.pypirc # shitty hack because of a bug in twine
rm -rf dist/
/venv/build/bin/python libs/tcp/setup.py bdist_wheel
/venv/build/bin/twine upload --repository-url http://server:8080 --username foo --password bar dist/*
