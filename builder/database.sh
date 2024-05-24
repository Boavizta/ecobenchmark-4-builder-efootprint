
#!/bin/bash

if test "$#" -ne 0; then
  echo "Invalid number of arguments..."
  echo
  echo "Usage: ./builder/database.sh"
  echo
  echo "Available tags:"
  echo "default (the use case to compare to)"
  echo
  exit 1
fi

export ORG=${ORG:-jdrouet}

echo "Building database"

docker buildx build --push --tag "$ORG/eco-benchmark:database" ./migrations

exit 0

