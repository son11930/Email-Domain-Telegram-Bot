#!/usr/bin/env bash
set -eu

service_name="${1:-}"
case "$service_name" in
  bot|worker|web) ;;
  *) echo "Usage: run-screen-service.sh {bot|worker|web}" >&2; exit 64 ;;
esac

project_dir="/opt/team-mail-bot"
mkdir -p "$project_dir/logs"
exec /usr/bin/screen -D -mS "team-mail-$service_name" /bin/bash -lc \
  "cd '$project_dir' && exec .venv/bin/team-mail '$service_name' >> logs/'$service_name'.log 2>&1"
