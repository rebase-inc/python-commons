#!/bin/sh
cd libs
find . -type d -mindepth 1 -exec basename {} \; | \
xargs -I {} python {}_setup.py bdist_wheel --universal --dist-dir /usr/src/app/wheels
