#!/bin/sh
echo 'Starting a new build...'
sleep 5
touch ~/.pypirc # shitty hack because of a bug in twine
rm -rf dist/
for file in ./libs/* ; do
  if [ -e "$file/setup.py" ] ; then
    /venv/build/bin/python $file/setup.py bdist_wheel
  fi
done
/venv/build/bin/twine upload --repository-url http://pycommons_server:8080 --username foo --password bar dist/*
rm -rf build/
rm -rf *egg-info
