#!/bin/sh
set -eu

# The benchmark's shared migrations image owns the schema by default.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  bundle exec rails db:migrate
fi

exec "$@"
