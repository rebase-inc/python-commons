#!/bin/sh
echo 'Starting a new build...'

printf 'Waiting for pypi server to come up...'
until $(curl --output /dev/null --silent --head --fail http://pypi_server:8080); do
  printf '.'
  sleep 0.5
done
printf '\n'

touch ~/.pypirc # shitty hack because of a bug in twine
rm -rf dist/
for file in ./libs/* ; do
  if [ -e "$file/setup.py" ] ; then
    /venv/build/bin/python $file/setup.py bdist_wheel
  fi
done
/venv/build/bin/twine upload --skip-existing --repository-url http://pypi_server:8080 --username foo --password bar dist/*
rm -rf build/
rm -rf *egg-info
