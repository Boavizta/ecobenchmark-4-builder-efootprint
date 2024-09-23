#!/bin/bash

if test "$#" -ne 0; then
  echo "Invalid number of arguments..."
  echo
  echo "Usage: ./builder/service.sh "
  echo
  echo
  exit 1
fi

export ORG=${ORG:-boavizta}


folder_path=./service

folder_names=$(find $folder_path -mindepth 1 -maxdepth 1 -type d -exec basename {} \;)
for service in $folder_names; do
  if [[ $folder_name != *mysql ]]; then #temp patch
      echo "Building service $service"
      docker buildx build --push --tag "ghcr.io/$ORG/ecobenchmark-4-builder-efootprint:service-$service" ./service/$service
  fi
done

exit 0

