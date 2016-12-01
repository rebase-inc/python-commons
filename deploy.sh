#!/bin/bash

build_images() {
  docker --log-level=warn build --quiet -t pycommons-builder builder/
  docker --log-level=warn build --quiet -t pycommons-server server/
  docker-compose -f $1 build
  docker-compose -f $1 up -d
}

RED="\033[0;31m"
NC="\033[0m"

type=${1:-debug}

if [ $type = "debug" ]; then
  echo -e "${RED}Building development environment...${NC}"
  dockerfile="docker-compose.dev.yml" 
elif [ $type = "production" ]; then
  echo -e "${RED}Building production environment...${NC}"
  dockerfile="docker-compose.prod.yml" 
else 
  echo -e "${RED}Unknown build type $type${NC}"
  exit 1
fi

build_images $dockerfile
