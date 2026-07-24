#!/bin/sh

SERVICE_CONTAINER='scoutcam-web-service'
IMAGE_NAME='scoutcamwebservice-dev'

if [ "$(docker ps -a -q -f name=^${CONTAINER_NAME})" ]; then
  echo "Stopping and removing old container."
  # Stop container
  docker stop ${SERVICE_CONTAINER}
  # Delete container
  docker rm ${SERVICE_CONTAINER}
  echo "Deleting old image"
  # Delete image
  docker image rm ${IMAGE_NAME}
fi


# Build new image
docker build -t ${IMAGE_NAME} .
# Run new image
docker run \
-p 8000:8000 \
--network scoutcam-network \
--env-file .env-docker \
--name ${SERVICE_CONTAINER} \
${IMAGE_NAME}

# -v /home/alex/.aws:/home/appuser/.aws:ro \