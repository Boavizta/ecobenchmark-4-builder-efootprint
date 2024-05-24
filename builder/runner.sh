
#!/bin/bash

if test "$#" -ne 0; then
  echo "Invalid number of arguments..."
  echo
  echo "Usage: ./builder/runner.sh"
  echo
  exit 1
fi

export ORG=${ORG:-boavizta}


docker buildx build --push --tag "ghcr.io/$ORG/ecobenchmark-4-builder-efootprint:runner" ./runner

exit 0