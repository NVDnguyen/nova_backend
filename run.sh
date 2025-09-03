#!/bin/bash
# remove old mongo server and redis server
docker stop shopping-cart-backend shopping-cart-worker mongo-db redis-cache
docker rm shopping-cart-backend shopping-cart-worker mongo-db redis-cache

# build
docker-compose down
echo "Rebuilding services with Docker Compose..."
sudo docker compose up --build -d