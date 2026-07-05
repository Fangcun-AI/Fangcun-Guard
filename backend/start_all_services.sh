#!/bin/bash
set -u

command -v python3 >/dev/null || { echo "Python3 is required"; exit 1; }
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

python3 migrations/run_migrations.py || echo "Migration check failed; continuing startup"

PIDS=()
for service in detection admin proxy; do
    python3 "start_${service}_service.py" &
    pid=$!
    PIDS+=("$pid")
    echo "Started ${service} service (PID ${pid})"
    sleep 1
done

echo "${PIDS[*]}" > /tmp/fangcunguard_services.pid
stop_services() {
    echo "Stopping services"
    kill "${PIDS[@]}" 2>/dev/null
}
trap stop_services INT TERM EXIT
wait
