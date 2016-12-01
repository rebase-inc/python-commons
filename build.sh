docker build -t pycommons-builder builder/
docker build -t pycommons-server server/
docker-compose build
docker-compose up -d
