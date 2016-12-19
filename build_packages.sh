#!/bin/sh
for dir in /usr/src/app/libs/*/ ; do
  if [ -e "$dir/setup.py" ] ; then
    cd $dir
    python setup.py --quiet bdist_wheel --universal --dist-dir /usr/src/app/build
  fi
done
