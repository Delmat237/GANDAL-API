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

## Endpoints et rôles autorisés

Préfixe API : `/api/v1`.

Rôles utilisés :

- **Public** : aucune authentification requise.
- **Authentifié** : tout utilisateur connecté (`Student` ou `Teacher`).
- **Student** : utilisateur étudiant.
- **Teacher** : utilisateur enseignant.
- **Admin/SuperAdmin** : enseignant dont `role` vaut `Admin` ou `SuperAdmin`.
- **Propriétaire** : utilisateur rattaché à la ressource concernée.
- **Enseignant assigné** : enseignant associé à la requête.

### Auth

- **Public** — `POST /auth/login` : connexion.
- **Public + `SUPERADMIN_SECRET_KEY`** — `POST /auth/register-admin` : création d'un administrateur de bootstrap.
- **Authentifié** — `GET /auth/me` : profil de l'utilisateur connecté.

### Users

- **Admin/SuperAdmin** — `POST /users/students` : créer un étudiant.
- **Admin/SuperAdmin** — `GET /users/students` : lister les étudiants.
- **Admin/SuperAdmin** — `GET /users/students/{student_id}` : consulter un étudiant.
- **Admin/SuperAdmin** — `PATCH /users/students/{student_id}` : modifier un étudiant.
- **Admin/SuperAdmin** — `DELETE /users/students/{student_id}` : supprimer un étudiant.
- **Admin/SuperAdmin** — `POST /users/teachers` : créer un enseignant.
- **Authentifié** — `GET /users/teachers` : lister les enseignants.
- **Admin/SuperAdmin** — `GET /users/teachers/{teacher_id}` : consulter un enseignant.
- **Admin/SuperAdmin** — `PATCH /users/teachers/{teacher_id}` : modifier un enseignant.
- **Admin/SuperAdmin** — `DELETE /users/teachers/{teacher_id}` : supprimer un enseignant.

### VMs

- **Admin/SuperAdmin** — `POST /vms` : créer une VM directement.
- **Authentifié** — `GET /vms` : lister les VMs visibles. Admin/SuperAdmin voient tout, les autres voient leurs VMs.
- **Propriétaire ou Admin/SuperAdmin** — `GET /vms/{vm_id}` : consulter une VM.
- **Propriétaire ou Admin/SuperAdmin** — `PATCH /vms/{vm_id}` : modifier une VM.
- **Propriétaire ou Admin/SuperAdmin** — `DELETE /vms/{vm_id}` : supprimer une VM.
- **Propriétaire ou Admin/SuperAdmin** — `POST /vms/{vm_id}/start` : démarrer une VM.
- **Propriétaire ou Admin/SuperAdmin** — `POST /vms/{vm_id}/stop` : arrêter une VM.
- **Propriétaire ou Admin/SuperAdmin** — `POST /vms/{vm_id}/pause` : mettre une VM en attente.

### Requêtes

- **Student** — `POST /requetes/create-vm` : demander la création d'une VM.
- **Student propriétaire de la VM** — `POST /requetes/delete-vm` : demander la suppression d'une VM.
- **Student** — `POST /requetes/account` : demander la création d'un compte.
- **Authentifié** — `GET /requetes` : lister les requêtes visibles. Admin/SuperAdmin voient tout, les étudiants voient leurs demandes, les enseignants voient les demandes qui leur sont assignées.
- **Étudiant auteur, enseignant assigné ou Admin/SuperAdmin** — `GET /requetes/{requete_id}` : consulter une requête.
- **Enseignant assigné ou Admin/SuperAdmin** — `POST /requetes/{requete_id}/approve` : approuver une requête.
- **Enseignant assigné ou Admin/SuperAdmin** — `POST /requetes/{requete_id}/reject` : rejeter une requête.

### Publications

- **Public** — `GET /publications/public` : lister les publications publiées.
- **Teacher ou Admin/SuperAdmin** — `POST /publications` : créer une publication.
- **Authentifié** — `GET /publications` : lister les publications visibles. Admin/SuperAdmin voient tout, les enseignants voient leurs publications, les étudiants voient les publications publiées.
- **Authentifié** — `GET /publications/{publication_id}` : consulter une publication publiée. Les brouillons/archives sont réservés à l'enseignant propriétaire ou Admin/SuperAdmin.
- **Enseignant propriétaire ou Admin/SuperAdmin** — `PATCH /publications/{publication_id}` : modifier une publication.
- **Enseignant propriétaire ou Admin/SuperAdmin** — `DELETE /publications/{publication_id}` : supprimer une publication.

### DNS

- **Admin/SuperAdmin** — `GET /dns` : lister toutes les entrées DNS.
- **Propriétaire de la VM ou Admin/SuperAdmin** — `GET /dns/vms/{vm_id}` : lister les entrées DNS d'une VM.
- **Propriétaire de la VM ou Admin/SuperAdmin** — `POST /dns` : créer une entrée DNS pour une VM.
- **Propriétaire de la VM ou Admin/SuperAdmin** — `GET /dns/{dns_id}` : consulter une entrée DNS.
- **Propriétaire de la VM ou Admin/SuperAdmin** — `PATCH /dns/{dns_id}` : modifier une entrée DNS.
- **Propriétaire de la VM ou Admin/SuperAdmin** — `DELETE /dns/{dns_id}` : supprimer une entrée DNS.

### Santé

- **Public** — `GET /health` : vérifier que l'API répond.
- **Public** — `GET /ready` : vérifier l'état de disponibilité de l'API et de la base de données.

## Variables d'environnement

Voir [`.env.example`](.env.example).
