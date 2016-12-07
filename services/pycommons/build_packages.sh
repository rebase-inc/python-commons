#!/bin/sh
for dir in /workdir/libs/*/ ; do
  if [ -e "$dir/setup.py" ] ; then
    echo ">>> BUILDING $dir <<<"
    cd $dir
    python setup.py bdist_wheel --universal --dist-dir /wheelhouse
  fi
done
