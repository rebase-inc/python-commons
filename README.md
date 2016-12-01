# ./build.sh devbuild
docker-compose -f build.dev.yml build
docker-compose -f build.dev.yml up -d

# ./build.sh build
docker-compose -f build.yml build
docker-compose -f build.yml up -d

# ./build.sh prod
docker-compose -f build.yml build
docker-compose -f build.yml up -d
docker-compose -f prod.yml build
docker-compose -f prod.yml up -d

# ./build.sh dev
docker-compose -f build.yml build
docker-compose -f build.yml up -d
docker-compose -f dev.yml build
docker-compose -f dev.yml up -d
