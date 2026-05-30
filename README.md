# dc-backend

API FastAPI (VSA) pour la gestion de VMs pédagogiques, requêtes et publications.

## Prérequis

- Python 3.12
- Docker & Docker Compose (recommandé en local)

## Démarrage local (Docker)

```bash
cp .env.example .env
docker compose up --build
```

API : <http://localhost:8000>  
Docs : <http://localhost:8000/docs>  
Health : <http://localhost:8000/health>

## Démarrage local (sans Docker)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql://dc:dc@localhost:5432/dc_backend
alembic upgrade head
uvicorn app.main:app --reload
```

## Seed développement

```bash
python scripts/seed_dev.py
```

Comptes par défaut : `admin` / `teacher` / `student` — mot de passe : `changeme123`

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Déploiement Render

1. Connecter le dépôt à Render
2. Utiliser le Blueprint [`render.yaml`](render.yaml)
3. Configurer les secrets SMTP et Proxmox dans le dashboard

Les migrations s'exécutent au démarrage : `alembic upgrade head`.

## Exemples curl

```bash
# Login
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"student","password":"changeme123"}'

# Approuver une requête (token admin)
curl -s -X POST http://localhost:8000/api/v1/requetes/1/approve \
  -H "Authorization: Bearer <token>"
```

## Règle RAccount

Après validation d'une `RAccount` : si `matricule` est renseigné → création **Student**, sinon si `role` est renseigné → **Teacher**.

## Variables d'environnement

Voir [`.env.example`](.env.example).
