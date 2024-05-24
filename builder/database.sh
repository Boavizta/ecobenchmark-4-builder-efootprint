
#!/bin/bash

if test "$#" -ne 0; then
  echo "Invalid number of arguments..."
  echo
  echo "Usage: ./builder/database.sh"
  echo
  exit 1
fi

export ORG=${ORG:-boavizta}

echo "Building database"

docker buildx build --push --tag "ghcr.io/$ORG/ecobenchmark-4-builder-efootprint:database" ./migrations

exit 0

