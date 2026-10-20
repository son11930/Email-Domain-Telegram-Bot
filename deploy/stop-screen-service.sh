#!/usr/bin/env bash
set -eu

service_name="${1:-}"
case "$service_name" in
  bot|worker|web) ;;
  *) echo "Usage: stop-screen-service.sh {bot|worker|web}" >&2; exit 64 ;;
esac

session_name="team-mail-$service_name"
/usr/bin/screen -S "$session_name" -X stuff "$(printf '\003')" 2>/dev/null || exit 0

for _ in {1..15}; do
  if ! /usr/bin/screen -ls 2>/dev/null | /usr/bin/grep -Fq ".$session_name"; then
    exit 0
  fi
  /usr/bin/sleep 1
done
