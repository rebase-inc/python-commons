#!/bin/sh

cd libs


python setup.py \
    build \
    	-b /tmp/build/ \
    	-t /tmp/build_tmp \
    egg_info \
    	-e /tmp/egg_info \
    bdist \
    	-b /tmp/build_bdist \
    bdist_wheel \
	--universal \
	--keep-temp \
	--dist-dir /usr/src/app/wheels
