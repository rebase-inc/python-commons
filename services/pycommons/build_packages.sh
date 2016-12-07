#!/bin/sh
for dir in /workdir/libs/*/ ; do
  if [ -e "$dir/setup.py" ] ; then
    cd $dir
    python setup.py --quiet bdist_wheel --universal --dist-dir /wheelhouse
  fi
done
