#!/bin/bash
set -euo pipefail

if [ -z ${DOMJUDGE_VERSION:+ok} ]; then
    echo "Environment variable DOMJUDGE_VERSION is not provided, quitting."
    exit 1
fi

echo "Cleaning up Docker containers..."
containers=$(docker ps -aq --filter network=tmt-domjudge-test)
if [ -n "$containers" ]; then
  docker stop $containers
  docker rm $containers
fi
docker network prune -f
