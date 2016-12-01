#!/bin/bash

build_images() {
  docker-compose "${@}" build
  docker-compose "${@}" up -d
}

RED="\033[0;31m"
NC="\033[0m"

type=${!#:-build}
args=${@:1:$#-1}

if [ $type = "devbuild" ]; then
  echo -e "${RED}Building dev build environment...${NC}"
  build_images "-f" "composefiles/build.dev.yml" $args
elif [ $type = "build" ]; then
  echo -e "${RED}Building build environment...${NC}"
  build_images "-f" "composefiles/build.yml" $args
elif [ $type = "prod" ]; then
  echo -e "${RED}This repository does not include any production products...${NC}"
  exit 1
elif [ $type = "dev" ]; then
  echo -e "${RED}This repository does not include any production products...${NC}"
  exit 1
else 
  echo -e "${RED}Unknown build type $type${NC}"
  exit 1
fi
