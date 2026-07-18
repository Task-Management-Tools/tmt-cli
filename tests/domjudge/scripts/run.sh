#!/bin/bash
set -euo pipefail

if docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE=(docker-compose)
else
    echo "No docker compose found"
    exit 1
fi

if [ -z ${DOMJUDGE_VERSION:+ok} ]; then
    echo "Environment variable DOMJUDGE_VERSION is not provided, quitting."
    exit 1
fi

export MYSQL_ROOT_PASSWORD=root
export MYSQL_PASSWORD=pass

echo Starting database and DOMjudge server...
"${DOCKER_COMPOSE[@]}" up -d
docker pull domjudge/judgehost:$DOMJUDGE_VERSION

echo Waiting until the DOMjudge server is healthy...
timeout 30 bash -c '
until [[ $(docker inspect -f {{.State.Health.Status}} domjudge-server) == "healthy" ]]; do
    sleep 1;
done
'

ADMIN_PASSWORD=$(docker exec domjudge-server cat /opt/domjudge/domserver/etc/initial_admin_password.secret | tr -d '\r')
JUDGEDAEMON_PASSWORD=$(docker exec domjudge-server cat /opt/domjudge/domserver/etc/restapi.secret | awk '!/^#/ {print $4}')
echo Admin password is $ADMIN_PASSWORD
echo Judgedaemon password is $JUDGEDAEMON_PASSWORD

docker run -itd \
    --privileged \
    --cgroupns=host \
    --hostname judgedaemon-0 \
    --name domjudge-judgehost-0 \
    --network tmt-domjudge-test \
    -v /sys/fs/cgroup:/sys/fs/cgroup \
    -e DAEMON_ID=0 \
    -e JUDGEDAEMON_PASSWORD=$JUDGEDAEMON_PASSWORD \
    -e DOMSERVER_BASEURL=http://domjudge-server/ \
    domjudge/judgehost:$DOMJUDGE_VERSION

curl --user "admin:$ADMIN_PASSWORD" \
    -X POST localhost:8888/api/v4/users/accounts \
    -F yaml=@accounts.yaml \
    -H 'accept: application/json' && echo
