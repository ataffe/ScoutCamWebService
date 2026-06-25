#!/bin/sh
if ! docker network inspect scoutcam-network >/dev/null 2>&1; then
  docker network create scoutcam-network
fi
docker run -e POSTGRES_DB=scoutcamservicedb \
 -p 5432:5432 \
 -e POSTGRES_USER=appuser \
 -e POSTGRES_PASSWORD=lYr3KCPu6QFr8W9KHcRF7gAK2Wfp \
 --name scoutcam-postgres \
 --network scoutcam-network \
 postgres