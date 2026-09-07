#!/bin/bash

# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# Git Bash rewrites container-side paths such as /var/lib/postgresql into Windows ones without these.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

# Everything lives in this brace group so that bash parses the whole file before running any of it:
# a run takes the better part of an hour, and without this, editing the file underneath a running
# copy derails it, since bash otherwise reads the script as it goes.
{

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

NAMESPACE=${NAMESPACE:-spellbook-prod}
POD_SELECTOR=${POD_SELECTOR:-app=spellbook-api}
POD_CONTAINER=${POD_CONTAINER:-spellbook-api-app}
DUMP_DIR=${DUMP_DIR:-$REPO_ROOT/temp}
# Never written to, only read: the script takes the current context unless this names another one,
# and it never runs kubectl config, so the kubeconfig is left exactly as it was found.
KUBE_CONTEXT=${KUBE_CONTEXT:-}
SECRET_NAME=${SECRET_NAME:-api-secrets}
POD_SERVICE_ACCOUNT=${POD_SERVICE_ACCOUNT:-app-service-account}
PGDUMP_IMAGE=${PGDUMP_IMAGE:-postgres:18-alpine}
# The helper job stops itself and is garbage collected at this age, so a machine that dies
# mid-dump still leaves nothing running in the cluster.
PGDUMP_DEADLINE=${PGDUMP_DEADLINE:-3600}
PGRESTORE_JOBS=${PGRESTORE_JOBS:-4}
PG_IMAGE=${PG_IMAGE:-postgres:18-alpine}
PG_CONTAINER=${PG_CONTAINER:-spellbook-pg-dev}
PG_HOST_PORT=${PG_HOST_PORT:-5433}
PG_DB=${PG_DB:-spellbook_db_test}
PG_USER=${PG_USER:-test_user}
PG_PASSWORD=${PG_PASSWORD:-test_password}
PG_VOLUME_PREFIX=${PG_VOLUME_PREFIX:-spellbook_pgdata}
# These change query plans, so keep them close to the RDS instance when comparing timings with production.
PG_SHARED_BUFFERS=${PG_SHARED_BUFFERS:-1GB}
PG_EFFECTIVE_CACHE_SIZE=${PG_EFFECTIVE_CACHE_SIZE:-3GB}
PG_WORK_MEM=${PG_WORK_MEM:-64MB}
PG_MAINTENANCE_WORK_MEM=${PG_MAINTENANCE_WORK_MEM:-1GB}
PYTHON_BIN=${PYTHON_BIN:-}

EXCLUDES=(
    contenttypes
    auth.permission
    admin.logentry
    sessions.session
    token_blacklist
    django_tasks_database
    social_django
)

# The pg_dump counterpart of EXCLUDES: the schema of these is kept, their rows are not.
PGDUMP_EXCLUDE_DATA=(
    django_session
    django_admin_log
    'social_auth_*'
    'token_blacklist_*'
    'django_tasks_*'
)

# RDS carries extensions the postgres image has no library for, and pg_restore counts each one it
# cannot create as an error. None of them hold data, so they are left out of the dump entirely.
PGDUMP_EXCLUDE_EXTENSIONS=(pg_repack)

METHOD=${METHOD:-pgdump}
FORCE_DUMP=0
DUMP_ONLY=0
LOAD_FILE=
SCRUB=0
ASSUME_YES=0

CLEANUP_JOB=
CLEANUP_FILE=
CREATED_CONTAINER=
CREATED_VOLUME=
INTERRUPTED=0
LOAD_DONE=0

usage() {
    cat <<'USAGE'
Usage: snapshot-prod-db.sh [options]

Downloads a snapshot of the production database through an API pod and loads it
into a brand new Postgres volume in Docker.

Options:
  --method METHOD     pgdump (default) runs pg_dump against RDS from a throwaway job and
                      restores it with pg_restore; dumpdata streams a Django fixture out of
                      an API pod instead, which creates nothing in the cluster but is far slower
  --force-dump        Download again even if today's snapshot is already in temp/
  --dump-only         Stop after the download, don't touch Docker
  --load-only FILE    Skip production entirely and load an existing snapshot
  --exclude LABEL     Add an app or model label to the dumpdata exclusions (repeatable)
  --scrub             Blank user emails and passwords once loaded
  --yes               Don't ask for confirmation
  -h, --help          Show this help

The cluster is only ever read from: the kubeconfig is never written, no context is switched,
and the one object pgdump creates is deleted again on the way out, including on Ctrl-C.

Environment overrides:
  NAMESPACE POD_SELECTOR POD_CONTAINER DUMP_DIR PYTHON_BIN KUBE_CONTEXT
  SECRET_NAME POD_SERVICE_ACCOUNT PGDUMP_IMAGE PGDUMP_DEADLINE PGRESTORE_JOBS
  PG_IMAGE PG_CONTAINER PG_HOST_PORT PG_DB PG_USER PG_PASSWORD PG_VOLUME_PREFIX
  PG_SHARED_BUFFERS PG_EFFECTIVE_CACHE_SIZE PG_WORK_MEM PG_MAINTENANCE_WORK_MEM
USAGE
}

log() {
    printf '\033[1;34m==>\033[0m [%s] %s\n' "$(date -u +%H:%M:%S)" "$1" >&2
}

warn() {
    printf '\033[1;33mwarning:\033[0m %s\n' "$1" >&2
}

die() {
    printf '\033[1;31merror:\033[0m %s\n' "$1" >&2
    exit 1
}

confirm() {
    if [ "$ASSUME_YES" -eq 1 ]; then
        return 0
    fi
    if [ ! -e /dev/tty ]; then
        die "$1 (pass --yes to answer this without a terminal)"
    fi
    local reply
    printf '%s [y/N] ' "$1" >&2
    read -r reply < /dev/tty
    case "$reply" in
        [yY] | [yY][eE][sS]) return 0 ;;
        *) die 'Aborted.' ;;
    esac
}

require() {
    command -v "$1" > /dev/null 2>&1 || die "$1 is required but is not on PATH"
}

# Docker and a Windows Python both need a native path; under Linux the path already is one.
native_path() {
    if command -v cygpath > /dev/null 2>&1; then
        cygpath --mixed "$1"
    else
        printf '%s' "$1"
    fi
}

kube() {
    if [ -n "$KUBE_CONTEXT" ]; then
        kubectl --context "$KUBE_CONTEXT" --namespace "$NAMESPACE" "$@"
    else
        kubectl --namespace "$NAMESPACE" "$@"
    fi
}

cleanup() {
    local status=$?
    trap - EXIT
    trap '' INT TERM HUP
    if [ -n "$CLEANUP_JOB" ]; then
        log "Deleting job $CLEANUP_JOB from $NAMESPACE"
        kube delete job "$CLEANUP_JOB" --ignore-not-found --cascade=foreground --timeout=120s > /dev/null 2>&1 ||
            warn "Could not delete it, do it by hand: kubectl --namespace $NAMESPACE delete job $CLEANUP_JOB"
        CLEANUP_JOB=
    fi
    if [ -n "$CLEANUP_FILE" ]; then
        rm -f "$CLEANUP_FILE"
        CLEANUP_FILE=
    fi
    # An error keeps its half-loaded database around to be looked at; an interrupt is a request to stop, so it goes.
    if [ "$INTERRUPTED" -eq 1 ] && [ "$LOAD_DONE" -eq 0 ] && [ -n "$CREATED_CONTAINER" ]; then
        log "Removing the unfinished $CREATED_CONTAINER and its volume $CREATED_VOLUME"
        docker rm --force "$CREATED_CONTAINER" > /dev/null 2>&1 || true
        docker volume rm "$CREATED_VOLUME" > /dev/null 2>&1 || true
    fi
    exit "$status"
}

interrupted() {
    INTERRUPTED=1
    warn 'Interrupted, cleaning up'
    exit 130
}

human_size() {
    local bytes
    bytes=$(stat -c %s "$1" 2> /dev/null || stat -f %z "$1")
    if command -v numfmt > /dev/null 2>&1; then
        numfmt --to=iec --suffix=B "$bytes"
    else
        printf '%s bytes' "$bytes"
    fi
}

pick_python() {
    if [ -n "$PYTHON_BIN" ]; then
        printf '%s' "$PYTHON_BIN"
        return
    fi
    local candidate
    for candidate in "$REPO_ROOT/backend/.venv/Scripts/python.exe" "$REPO_ROOT/backend/.venv/bin/python"; do
        if [ -x "$candidate" ]; then
            printf '%s' "$candidate"
            return
        fi
    done
    command -v python3 || command -v python || die 'No Python found: run uv sync in backend/, or set PYTHON_BIN'
}

pick_pod() {
    kube get pods \
        --selector "$1" \
        --field-selector=status.phase=Running \
        --output name |
        head -n 1 |
        cut -d / -f 2
}

find_todays_dump() {
    ls -1t "$DUMP_DIR"/spellbook-prod-"$(date -u +%Y%m%d)"T*."$SNAPSHOT_EXT" 2> /dev/null | head -n 1 || true
}

# Streams the pod's stdout into the snapshot, through pv when it is around to show progress.
stream_into_snapshot() {
    local partial=$1
    shift
    CLEANUP_FILE=$partial
    if command -v pv > /dev/null 2>&1; then
        kube exec "$@" | pv > "$partial"
    else
        kube exec "$@" > "$partial"
    fi
}

dump_with_dumpdata() {
    local pod
    pod=$(pick_pod "$POD_SELECTOR")
    [ -n "$pod" ] || die "No running pod matches $POD_SELECTOR in $NAMESPACE"
    kube wait --for=condition=Ready --timeout=60s "pod/$pod" > /dev/null

    confirm "Run dumpdata on $pod in $NAMESPACE? It reads every table of the production database."

    local remote_command='python manage.py dumpdata'
    local label
    for label in "${EXCLUDES[@]}"; do
        remote_command="$remote_command --exclude $label"
    done
    # jsonl keeps both ends streaming; a single json array would be held whole in memory by loaddata.
    remote_command="$remote_command --database default --format jsonl --natural-foreign | gzip --stdout"

    log "Dumping through $pod into $DUMP_FILE"
    stream_into_snapshot "$DUMP_FILE.part" "$pod" --container "$POD_CONTAINER" -- sh -c "$remote_command"
    gzip --test "$DUMP_FILE.part" || die 'The downloaded snapshot is truncated'
}

dump_with_pgdump() {
    confirm "Create a temporary pg_dump job in $NAMESPACE? It reads the whole production database and is deleted afterwards."

    # Object names are RFC 1123, so the T and Z of the timestamp have to come down to lower case.
    local job
    job=spellbook-pgdump-$(printf '%s' "$TIMESTAMP" | tr 'A-Z' 'a-z')
    log "Creating job $job"
    CLEANUP_JOB=$job
    kube create --filename - > /dev/null <<MANIFEST
apiVersion: batch/v1
kind: Job
metadata:
  name: $job
  namespace: $NAMESPACE
spec:
  backoffLimit: 0
  activeDeadlineSeconds: $PGDUMP_DEADLINE
  ttlSecondsAfterFinished: 0
  template:
    metadata:
      labels:
        app: spellbook-pgdump
        snapshot: '$TIMESTAMP'
    spec:
      serviceAccountName: $POD_SERVICE_ACCOUNT
      restartPolicy: Never
      containers:
        - name: pgdump
          image: $PGDUMP_IMAGE
          command: ['sleep', '$PGDUMP_DEADLINE']
          env:
            - name: PGHOST
              valueFrom:
                secretKeyRef:
                  name: $SECRET_NAME
                  key: db-host
            - name: PGPORT
              valueFrom:
                secretKeyRef:
                  name: $SECRET_NAME
                  key: db-port
            - name: PGDATABASE
              valueFrom:
                secretKeyRef:
                  name: $SECRET_NAME
                  key: db-name
            - name: PGUSER
              valueFrom:
                secretKeyRef:
                  name: $SECRET_NAME
                  key: db-user
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: $SECRET_NAME
                  key: db-password
MANIFEST

    log 'Waiting for the job pod'
    kube wait --for=condition=Ready pod \
        --selector "app=spellbook-pgdump,snapshot=$TIMESTAMP" \
        --timeout=300s > /dev/null

    local pod
    pod=$(pick_pod "app=spellbook-pgdump,snapshot=$TIMESTAMP")
    [ -n "$pod" ] || die 'The pg_dump job produced no running pod'
    log "Connected to $(kube exec "$pod" -- psql --tuples-only --no-align --command 'select version()')"

    local dump_args=(--format=custom --no-owner --no-privileges --no-tablespaces)
    local pattern
    for pattern in "${PGDUMP_EXCLUDE_DATA[@]}"; do
        dump_args+=(--exclude-table-data="$pattern")
    done
    for pattern in "${PGDUMP_EXCLUDE_EXTENSIONS[@]}"; do
        dump_args+=(--exclude-extension="$pattern")
    done

    log "Dumping through $pod into $DUMP_FILE"
    stream_into_snapshot "$DUMP_FILE.part" "$pod" -- pg_dump "${dump_args[@]}"
    # pg_restore is the real check; this catches a stream that died before writing anything usable.
    [ "$(head -c 5 "$DUMP_FILE.part")" = 'PGDMP' ] || die 'The downloaded snapshot is not a pg_dump archive'
}

dump_from_production() {
    log "Cluster: ${KUBE_CONTEXT:-$(kubectl config current-context)}"
    kube get pods >&2
    mkdir -p "$DUMP_DIR"

    case "$METHOD" in
        dumpdata) dump_with_dumpdata ;;
        pgdump) dump_with_pgdump ;;
    esac

    mv "$DUMP_FILE.part" "$DUMP_FILE"
    CLEANUP_FILE=
    chmod 600 "$DUMP_FILE"
}

psql_exec() {
    docker exec --env PGPASSWORD="$PG_PASSWORD" "$PG_CONTAINER" \
        psql --username "$PG_USER" --dbname "$PG_DB" --no-psqlrc --quiet --set ON_ERROR_STOP=1 "$@"
}

start_postgres() {
    if docker container inspect "$PG_CONTAINER" > /dev/null 2>&1; then
        local old_volumes
        old_volumes=$(docker container inspect --format '{{range .Mounts}}{{.Name}} {{end}}' "$PG_CONTAINER")
        warn "Container $PG_CONTAINER already exists, on volume(s): $old_volumes"
        confirm "Remove the container $PG_CONTAINER? Its volumes are kept and can be reattached later."
        docker rm --force "$PG_CONTAINER" > /dev/null
    fi

    log "Creating volume $PG_VOLUME and container $PG_CONTAINER"
    docker volume create "$PG_VOLUME" > /dev/null
    CREATED_VOLUME=$PG_VOLUME
    CREATED_CONTAINER=$PG_CONTAINER
    docker run --detach \
        --name "$PG_CONTAINER" \
        --env POSTGRES_USER="$PG_USER" \
        --env POSTGRES_PASSWORD="$PG_PASSWORD" \
        --env POSTGRES_DB="$PG_DB" \
        --env PGPORT=5432 \
        --publish "$PG_HOST_PORT:5432" \
        --volume "$PG_VOLUME:/var/lib/postgresql" \
        --volume "$(native_path "$(dirname "$DUMP_FILE")"):/dump:ro" \
        --shm-size 1g \
        --restart unless-stopped \
        "$PG_IMAGE" \
        postgres \
        -c shared_buffers="$PG_SHARED_BUFFERS" \
        -c effective_cache_size="$PG_EFFECTIVE_CACHE_SIZE" \
        -c work_mem="$PG_WORK_MEM" \
        -c maintenance_work_mem="$PG_MAINTENANCE_WORK_MEM" \
        -c max_wal_size=8GB \
        -c checkpoint_timeout=30min > /dev/null

    local attempt
    for attempt in $(seq 1 60); do
        # Over TCP, not the socket: initdb runs a temporary server on the socket alone, and that one is not ready.
        if docker exec "$PG_CONTAINER" pg_isready --host 127.0.0.1 --username "$PG_USER" --dbname "$PG_DB" --quiet; then
            return 0
        fi
        sleep 2
    done
    die "$PG_CONTAINER did not become ready"
}

write_load_helpers() {
    mkdir -p "$REPO_ROOT/backend/temp"
    cat > "$REPO_ROOT/backend/temp/snapshot_stubs.py" <<'PYTHON'
import gzip
import json
import os
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
wanted = set()
with gzip.open(os.environ['SNAPSHOT_FILE'], 'rt', encoding='utf-8') as snapshot:
    for line in snapshot:
        record = json.loads(line)
        # Permissions are referenced from the auth models alone, and dumpdata emits those before the bulk.
        if record['model'].startswith('spellbook.'):
            break
        if record['model'] not in ('auth.group', 'auth.user'):
            continue
        for field in ('permissions', 'user_permissions'):
            for natural_key in record['fields'].get(field) or ():
                wanted.add(tuple(natural_key))
missing = wanted - {
    (permission.codename, permission.content_type.app_label, permission.content_type.model)
    for permission in Permission.objects.select_related('content_type')
}
for codename, app_label, model in sorted(missing):
    content_type, _ = ContentType.objects.get_or_create(app_label=app_label, model=model)
    Permission.objects.create(codename=codename, content_type=content_type, name=codename)
    print(f'stub permission {codename} on {app_label}.{model}')
PYTHON
    cat > "$REPO_ROOT/backend/temp/snapshot_settings.py" <<'PYTHON'
import sys
from pathlib import Path
# The image copies common/ next to the backend sources; from a checkout it has to be put on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from backend.production_settings import *  # noqa: E402,F401,F403
from backend.production_settings import DATABASES  # noqa: E402
# The production connection caps statements at 60s, which the constraint check closing loaddata exceeds,
# and its pool is pointless for a one-shot command.
DATABASES['default']['OPTIONS'] = {'options': '-c statement_timeout=0'}
DATABASES.pop('admin', None)
PYTHON
}

run_manage() {
    (
        cd "$REPO_ROOT/backend"
        DJANGO_SETTINGS_MODULE=snapshot_settings \
            PYTHONPATH=temp \
            SECRET_KEY=snapshot \
            SQL_ENGINE=django.db.backends.postgresql \
            SQL_DATABASE="$PG_DB" \
            SQL_USER="$PG_USER" \
            SQL_PASSWORD="$PG_PASSWORD" \
            SQL_HOST=127.0.0.1 \
            SQL_PORT="$PG_HOST_PORT" \
            SNAPSHOT_FILE="$(native_path "$DUMP_FILE")" \
            "$PYTHON" manage.py "$@"
    )
}

load_with_loaddata() {
    write_load_helpers

    log 'Applying migrations'
    run_manage migrate --noinput

    # Production keeps permissions for models that were removed from the code; migrate never recreates
    # those, and the groups holding them fail to load without something to point at.
    # shell reads a script from stdin on every platform but Windows, so hand it the file to exec instead.
    log 'Recreating permissions for models the code no longer defines'
    run_manage shell --command "exec(open('temp/snapshot_stubs.py', encoding='utf-8').read())"

    log "Loading $DUMP_FILE, the slow part: loaddata inserts row by row"
    run_manage loaddata "$(native_path "$DUMP_FILE")"
}

load_with_pgrestore() {
    # The schema travels inside the archive, so this one skips migrate entirely.
    log "Restoring $DUMP_FILE with pg_restore"
    docker exec --env PGPASSWORD="$PG_PASSWORD" "$PG_CONTAINER" \
        pg_restore \
        --username "$PG_USER" \
        --dbname "$PG_DB" \
        --no-owner \
        --no-privileges \
        --jobs "$PGRESTORE_JOBS" \
        "/dump/$(basename "$DUMP_FILE")"
}

load_snapshot() {
    log 'Turning durability off for the load'
    psql_exec --command 'ALTER SYSTEM SET fsync = off' \
        --command 'ALTER SYSTEM SET synchronous_commit = off' \
        --command 'ALTER SYSTEM SET full_page_writes = off' \
        --command 'ALTER SYSTEM SET autovacuum = off' \
        --command 'SELECT pg_reload_conf()' > /dev/null

    case "$METHOD" in
        dumpdata) load_with_loaddata ;;
        pgdump) load_with_pgrestore ;;
    esac

    if [ "$SCRUB" -eq 1 ]; then
        log 'Scrubbing user credentials'
        psql_exec --command "UPDATE auth_user SET password = '!', email = '', first_name = '', last_name = ''" > /dev/null
    fi

    log 'Restoring durability and collecting planner statistics'
    psql_exec --command 'ALTER SYSTEM RESET fsync' \
        --command 'ALTER SYSTEM RESET synchronous_commit' \
        --command 'ALTER SYSTEM RESET full_page_writes' \
        --command 'ALTER SYSTEM RESET autovacuum' \
        --command 'SELECT pg_reload_conf()' > /dev/null
    psql_exec --command 'VACUUM (ANALYZE)' > /dev/null
}

while [ $# -gt 0 ]; do
    case "$1" in
        --method)
            [ $# -ge 2 ] || die '--method needs dumpdata or pgdump'
            METHOD=$2
            shift
            ;;
        --force-dump) FORCE_DUMP=1 ;;
        --dump-only) DUMP_ONLY=1 ;;
        --load-only)
            [ $# -ge 2 ] || die '--load-only needs a file'
            LOAD_FILE=$2
            shift
            ;;
        --exclude)
            [ $# -ge 2 ] || die '--exclude needs a label'
            EXCLUDES+=("$2")
            shift
            ;;
        --scrub) SCRUB=1 ;;
        --yes | -y) ASSUME_YES=1 ;;
        -h | --help)
            usage
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
    shift
done

require docker
trap cleanup EXIT
trap interrupted INT TERM HUP

if [ -n "$LOAD_FILE" ]; then
    # The extension says how the file has to be loaded, whatever --method was asked for.
    case "$LOAD_FILE" in
        *.dump) METHOD=pgdump ;;
        *.jsonl.gz) METHOD=dumpdata ;;
    esac
fi

case "$METHOD" in
    dumpdata) SNAPSHOT_EXT=jsonl.gz ;;
    pgdump) SNAPSHOT_EXT=dump ;;
    *) die "Unknown method: $METHOD" ;;
esac

if [ -n "$LOAD_FILE" ]; then
    [ -f "$LOAD_FILE" ] || die "No such snapshot: $LOAD_FILE"
    DUMP_FILE=$(cd "$(dirname "$LOAD_FILE")" && pwd)/$(basename "$LOAD_FILE")
    TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
    log "Loading $DUMP_FILE with the $METHOD method"
else
    require kubectl
    EXISTING=
    if [ "$FORCE_DUMP" -eq 0 ]; then
        EXISTING=$(find_todays_dump)
    fi
    if [ -n "$EXISTING" ]; then
        DUMP_FILE=$EXISTING
        TIMESTAMP=$(basename "$DUMP_FILE" ".$SNAPSHOT_EXT")
        TIMESTAMP=${TIMESTAMP#spellbook-prod-}
        log "Reusing today's snapshot $DUMP_FILE ($(human_size "$DUMP_FILE")); pass --force-dump to take a new one"
    else
        TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
        DUMP_FILE=$DUMP_DIR/spellbook-prod-$TIMESTAMP.$SNAPSHOT_EXT
        dump_from_production
        log "Downloaded $DUMP_FILE ($(human_size "$DUMP_FILE"))"
    fi
fi

if [ "$DUMP_ONLY" -eq 1 ]; then
    log 'Stopping here, --dump-only was given'
    exit 0
fi

if [ "$METHOD" = dumpdata ]; then
    PYTHON=$(pick_python)
fi
PG_VOLUME=${PG_VOLUME_PREFIX}_$TIMESTAMP

start_postgres
load_snapshot
LOAD_DONE=1

log 'Snapshot loaded'
cat >&2 <<SUMMARY

  snapshot   $DUMP_FILE ($(human_size "$DUMP_FILE"), $METHOD)
  container  $PG_CONTAINER ($PG_IMAGE), snapshot directory mounted at /dump
  volume     $PG_VOLUME
  url        postgresql://$PG_USER:$PG_PASSWORD@127.0.0.1:$PG_HOST_PORT/$PG_DB
  psql       docker exec -it $PG_CONTAINER psql -U $PG_USER -d $PG_DB

Volumes from earlier runs are still there; drop the ones you no longer need with
  docker volume ls --filter name=$PG_VOLUME_PREFIX
  docker volume rm <volume>
SUMMARY

}
