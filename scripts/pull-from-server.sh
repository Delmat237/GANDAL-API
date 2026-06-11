#!/usr/bin/env bash
#
# Récupère le code applicatif depuis le serveur vers la machine locale.
# Inverse de scripts/deploy.sh (sans rebuild Docker).
#
# Usage :
#   ./scripts/pull-from-server.sh           # rsync serveur -> local
#   ./scripts/pull-from-server.sh --dry-run # aperçu sans écrire
#
# Préservé en local : .git/, .venv/, .env, docs/
# Non récupéré depuis le serveur : .env, docker-compose.prod.yml, build.log
#
set -euo pipefail

REMOTE="${REMOTE:-root@10.50.30.102}"
REMOTE_DIR="${REMOTE_DIR:-/gandal-dev}"
SSH_OPTS="-o BatchMode=yes -o ConnectTimeout=10"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    *) echo "Argument inconnu : $arg" >&2; exit 2 ;;
  esac
done

RSYNC_OPTS=(-az)
[ "$DRY_RUN" = 1 ] && RSYNC_OPTS+=(-n -v)

echo "==> Synchronisation $REMOTE:$REMOTE_DIR -> $PROJECT_DIR"
for i in 1 2 3 4 5; do
  rsync "${RSYNC_OPTS[@]}" \
    --exclude '.env' --exclude '.env.bak.*' \
    --exclude 'docker-compose.prod.yml' \
    --exclude 'build.log' --exclude 'deploy_retry.sh' \
    --exclude '.git/' --exclude '.venv/' --exclude '.venv_test/' \
    --exclude '.pytest_cache/' --exclude '__pycache__/' --exclude '*.pyc' \
    -e "ssh $SSH_OPTS" \
    "$REMOTE:$REMOTE_DIR/" ./ && break
  echo "[rsync retry $i]" >&2
  sleep 5
  [ "$i" = 5 ] && { echo "rsync a échoué" >&2; exit 1; }
done

echo "✅  Récupération terminée."
[ "$DRY_RUN" = 1 ] && echo "(dry-run : aucun fichier modifié)"
