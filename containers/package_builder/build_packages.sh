#!/bin/sh
echo '>>>>>> STARTING NEW BUILD <<<<<<'

printf 'Waiting for pypi server to come up...'
until $(curl --output /dev/null --silent --head --fail http://pypi_server:8080); do
  printf '.'
  sleep 0.5
done
printf '\n'

touch ~/.pypirc # shitty hack because of a bug in twine
rm -rf dist/
for dir in libs/*/ ; do
  if [ -e "$dir/setup.py" ] ; then
    echo ">>> BUILDING $dir <<<"
    /venv/build/bin/python $dir/setup.py bdist_wheel
  fi
done
ls 
/venv/build/bin/twine upload --skip-existing --repository-url http://pypi_server:8080 --username foo --password bar dist/*
rm -rf build/
rm -rf *egg-info
