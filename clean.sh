#!/bin/bash
docker-compose -f layouts/dev.yml -f layouts/pro.yml stop
docker-compose -f layouts/dev.yml -f layouts/pro.yml rm
