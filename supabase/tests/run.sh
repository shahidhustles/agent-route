#!/usr/bin/env bash
# Applies the migrations to a throwaway local Postgres and runs the RLS checks. Touches no Supabase project.
set -euo pipefail
cd "$(dirname "$0")"
name=relay-pg-test
docker rm -f $name >/dev/null 2>&1 || true
docker run -d --name $name -e POSTGRES_PASSWORD=x postgres:16 >/dev/null
trap 'docker rm -f $name >/dev/null' EXIT
until docker exec $name pg_isready -U postgres -q 2>/dev/null; do sleep 1; done
sleep 2
for f in stubs.sql ../migrations/*.sql rls.sql; do
  docker exec -i $name psql -U postgres -v ON_ERROR_STOP=1 -q -o /dev/null < "$f"
done 2>&1 | grep -E "^(NOTICE|ERROR)" | sed 's/^NOTICE:  //'
