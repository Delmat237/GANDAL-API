#!/usr/bin/env bash
#
# Déploiement / mise à jour de dc-backend (GANDAL-API) sur le serveur.
#
# Usage :
#   ./scripts/deploy.sh              # rsync du code + rebuild + recreate
#   ./scripts/deploy.sh --no-build   # rsync seulement (pas de rebuild image)
#   ./scripts/deploy.sh --logs       # déploie puis suit les logs de l'API
#
# Le code est synchronisé vers $REMOTE_DIR puis l'image est reconstruite.
# Les fichiers présents UNIQUEMENT sur le serveur (.env, docker-compose.prod.yml)
# sont préservés (exclus du --delete).
#
set -euo pipefail

# --- Configuration (surchargeable par variables d'environnement) ---------------
REMOTE="${REMOTE:-root@10.50.30.102}"
REMOTE_DIR="${REMOTE_DIR:-/gandal-dev}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
SSH_OPTS="-o BatchMode=yes -o ConnectTimeout=10"

# Répertoire du projet (parent de scripts/)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

DO_BUILD=1
FOLLOW_LOGS=0
for arg in "$@"; do
  case "$arg" in
    --no-build) DO_BUILD=0 ;;
    --logs)     FOLLOW_LOGS=1 ;;
    *) echo "Argument inconnu : $arg" >&2; exit 2 ;;
  esac
done

# --- Wrappers avec retry (le lien réseau vers l'hôte est instable) -------------
ssh_retry() { local i; for i in 1 2 3 4 5; do ssh $SSH_OPTS "$REMOTE" "$@" && return 0; echo "[ssh retry $i]" >&2; sleep 5; done; return 1; }

echo "==> 1/3  Synchronisation du code -> $REMOTE:$REMOTE_DIR"
for i in 1 2 3 4 5; do
  rsync -az --delete \
    --exclude '.git/' --exclude '.venv/' --exclude '.venv_test/' \
    --exclude '.pytest_cache/' --exclude '__pycache__/' --exclude '*.pyc' \
    --exclude '.env' --exclude 'docs/' --exclude 'wheels/' \
    --exclude 'docker-compose.prod.yml' \
    --exclude 'build.log' --exclude 'deploy_retry.sh' \
    -e "ssh $SSH_OPTS" \
    ./ "$REMOTE:$REMOTE_DIR/" && break
  echo "[rsync retry $i]" >&2; sleep 5
  [ "$i" = 5 ] && { echo "rsync a échoué" >&2; exit 1; }
done

if [ "$DO_BUILD" = 1 ]; then
  echo "==> 2/3  Reconstruction de l'image + recréation des conteneurs"
  ssh_retry "cd '$REMOTE_DIR' && docker compose -f '$COMPOSE_FILE' up -d --build"
else
  echo "==> 2/3  (--no-build) Recréation des conteneurs sans rebuild"
  ssh_retry "cd '$REMOTE_DIR' && docker compose -f '$COMPOSE_FILE' up -d"
fi

echo "==> 3/3  Vérification"
ssh_retry "cd '$REMOTE_DIR' && docker compose -f '$COMPOSE_FILE' ps && \
  echo '--- health ---' && (until curl -s -m 3 http://127.0.0.1:8000/health; do sleep 2; done) && echo && \
  echo '--- ready ---' && curl -s -m 5 http://127.0.0.1:8000/ready && echo"

echo "✅  Déploiement terminé."

if [ "$FOLLOW_LOGS" = 1 ]; then
  echo "==> Logs (Ctrl-C pour quitter)"
  ssh $SSH_OPTS "$REMOTE" "cd '$REMOTE_DIR' && docker compose -f '$COMPOSE_FILE' logs -f --tail=50 api"
fi
