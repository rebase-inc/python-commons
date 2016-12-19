#!/bin/bash

build_images() {
  docker-compose "${@}" build
  docker-compose "${@}" up -d
}

RED="\033[0;31m"
NC="\033[0m"

type=${BASH_ARGV[0]:-dev}
args=${@:1:$#-1}

if [ $type = "dev" ]; then
  echo -e "${RED}Building development environment...${NC}"
  build_images "-f" "layouts/dev.yml" $args
elif [ $type = "pro" ]; then
  echo -e "${RED}Building production environment...${NC}"
  build_images "-f" "layouts/pro.yml" $args
else
  echo -e "${RED}Unknown build type $type${NC}"
  exit 1
fi
