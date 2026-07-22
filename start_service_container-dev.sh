#!/bin/sh
docker run \
-p 8000:8000 \
--network scoutcam-network \
--env-file .env-docker \
--name scoutcam-web-service \
scoutcamwebservice-dev

# -v /home/alex/.aws:/home/appuser/.aws:ro \