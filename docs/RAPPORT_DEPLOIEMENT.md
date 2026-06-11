# Rapport de déploiement — GANDAL-API (dc-backend)

| | |
|---|---|
| **Projet** | dc-backend — API FastAPI (VSA) de gestion de VMs pédagogiques, requêtes et publications |
| **Dépôt** | `github.com/Delmat237/GANDAL-API` |
| **Version déployée** | commit `1a48612` (`fix : anomali`) — branche `master` |
| **Environnement** | Serveur mutualisé `omega-test-3001` — `10.50.30.102` |
| **Date du déploiement** | 11 juin 2026 |
| **Type de déploiement** | Conteneurisé (Docker Compose), en isolation sur serveur partagé |
| **Statut final** | ✅ **En production — opérationnel et validé** |

---

## 1. Résumé exécutif

L'API GANDAL a été déployée avec succès sur le serveur `10.50.30.102` sous forme de
stack Docker Compose isolée, **sans aucun impact sur les applications tierces** déjà
hébergées sur la machine (stacks `iwm-*`, `erp-cashier-*`, `verifid`).

La solution expose l'API selon deux canaux complémentaires :

1. **Reverse-proxy mutualisé** (nginx `iwm-gateway`, port 80) — accès nominal de
   production via le sous-domaine `gandal.10.50.30.102.nip.io` ;
2. **Port hôte direct** `8000` — accès de diagnostic.

L'ensemble de la chaîne a été vérifié de bout en bout : démarrage des conteneurs,
exécution des migrations de base de données, points de santé applicatifs, routage du
reverse-proxy, création du compte d'administration et authentification. **Tous les
tests de recette sont au vert.**

---

## 2. Contexte et objectifs

| Objectif | Atteint |
|---|---|
| Déployer l'API sur `root@10.50.30.102` | ✅ |
| Ne pas perturber les services existants du serveur | ✅ |
| Exposer l'API derrière le reverse-proxy nginx existant | ✅ |
| Sécuriser les secrets de production (JWT, mot de passe admin, DB) | ✅ |
| Disposer d'un compte administrateur fonctionnel | ✅ |

---

## 3. Environnement cible

| Élément | Valeur |
|---|---|
| Hôte | `omega-test-3001` |
| Adresse IP | `10.50.30.102` |
| Système | Debian GNU/Linux 12 (bookworm) |
| Noyau | `6.1.0-49-cloud-amd64` |
| Moteur de conteneurs | Docker `29.5.3` |
| Orchestration | Docker Compose `v5.1.4` (plugin) |
| Stockage racine | 20 Go (≈ 87 % utilisés après déploiement) |
| Répertoire applicatif | `/gandal-dev` |

> **Note environnement partagé.** Le serveur héberge plusieurs stacks indépendantes
> (`iwm-app`, `iwm-postgres`, `iwm-kafka`, `iwm-elasticsearch`, `iwm-redis`,
> `erp-cashier-backend`, `erp-cashier-frontend`, `verifid-backend`, reverse-proxy
> `iwm-gateway`). Le déploiement a été conduit en stricte isolation.

---

## 4. Architecture de la solution déployée

```
                         Internet / LAN
                               │
                    http://gandal.10.50.30.102.nip.io   (port 80)
                               │
                 ┌─────────────▼──────────────┐
                 │   nginx  « iwm-gateway »    │  (reverse-proxy mutualisé)
                 │  routage par sous-domaine   │
                 │  map $host $svc {           │
                 │    ~^gandal\. → gandal-api  │   ← entrée ajoutée
                 │    ~^api\.    → iwm-app      │
                 │    ~^caisse\. → ...          │
                 │  }                           │
                 └─────────────┬──────────────┘
                               │ réseau Docker « iwm-vm-network » (172.18.0.0/16)
                               │
            ┌──────────────────▼───────────────────┐
            │  Stack Compose  « gandal »            │
            │                                        │
            │  ┌───────────────┐   ┌──────────────┐ │
   :8000 ───┼─▶│  gandal-api   │──▶│   gandal-db  │ │
  (accès    │  │  FastAPI      │   │ postgres:17  │ │
  direct)   │  │  172.18.0.10  │   │  (healthy)   │ │
            │  │  172.20.0.3   │   │  172.20.0.x  │ │
            │  └───────────────┘   └──────┬───────┘ │
            │       réseau « gandal-net » │         │
            │                       volume gandal_pgdata
            └────────────────────────────────────────┘
```

**Inventaire des conteneurs déployés**

| Conteneur | Image | Taille | Réseaux | Ports | Statut |
|---|---|---|---|---|---|
| `gandal-api` | `gandal-api:latest` (build local) | 311 Mo | `gandal-net`, `iwm-vm-network` | `0.0.0.0:8000→8000` | Up |
| `gandal-db` | `postgres:17-alpine` | 400 Mo | `gandal-net` | interne `5432` | Up (healthy) |

**Persistance** : volume Docker nommé `gandal_pgdata` (données PostgreSQL).

---

## 5. Procédure de déploiement réalisée

1. **Audit préalable du serveur** — vérification de l'accès SSH, de la présence de
   Docker / Compose, des ports hôtes disponibles (80 occupé par le gateway ; 8000 et
   5433 libres) et de l'absence d'un déploiement antérieur.
2. **Analyse du reverse-proxy existant** — identification du mécanisme de routage par
   sous-domaine (`map $host $svc`) et de la résolution DNS Docker sur le réseau
   `iwm-vm-network`.
3. **Transfert du code** — synchronisation du dépôt local vers `/gandal-dev` via
   `rsync` (exclusions : `.git/`, `.venv/`, caches, `docs/`, `.env`).
4. **Génération des secrets de production** — JWT, clé secrète SuperAdmin, mot de passe
   PostgreSQL et mot de passe administrateur (valeurs fortes aléatoires).
5. **Définition de la stack de production** — fichier `docker-compose.prod.yml` dédié
   (projet `gandal`, conteneurs nommés, raccordement au réseau du gateway, volume
   persistant, sondes de santé).
6. **Construction et démarrage** — `docker compose up -d --build` ; les migrations
   Alembic (`alembic upgrade head`) s'exécutent automatiquement au démarrage du
   conteneur API.
7. **Intégration au reverse-proxy** — ajout d'une entrée de routage `gandal.` dans
   `/root/iwm/ops/nginx/gateway.conf` (avec sauvegarde préalable), validation
   `nginx -t` puis rechargement à chaud `nginx -s reload`.
8. **Bootstrap applicatif** — création du compte SuperAdmin via
   `POST /api/v1/auth/register-admin`.
9. **Recette** — validation des points de santé, du routage et de l'authentification.

---

## 6. Configuration

### 6.1 Stack Docker Compose (`/gandal-dev/docker-compose.prod.yml`)

Caractéristiques notables :

- `name: gandal` — projet Compose isolé.
- Conteneurs nommés explicitement (`gandal-api`, `gandal-db`) pour la résolution DNS
  par le reverse-proxy.
- `restart: unless-stopped` — redémarrage automatique des services.
- Sonde de santé PostgreSQL (`pg_isready`) ; l'API ne démarre qu'une fois la base
  `healthy` (`depends_on: condition: service_healthy`).
- Raccordement de `gandal-api` au réseau externe `iwm-vm-network` (du gateway) **et**
  à un réseau privé `gandal-net` (communication avec la base).
- Publication de l'API sur `0.0.0.0:8000` (accès direct de diagnostic).

### 6.2 Variables d'environnement (`/gandal-dev/.env`)

| Variable | Valeur de production |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `postgresql://dc:***@db:5432/dc_backend` |
| `JWT_SECRET` | secret fort généré *(masqué)* |
| `SUPERADMIN_USERNAME` | `admin` |
| `SUPERADMIN_EMAIL` | `admin@enspy-gi.cm` |
| `SUPERADMIN_PASSWORD` | secret fort généré *(transmis séparément)* |
| `SUPERADMIN_SECRET_KEY` | secret fort généré *(masqué)* |
| `PROXMOX_ENABLED` | `false` (mode simulation) |
| `EMAIL_BACKEND` | `log` |
| `CORS_ORIGINS` | origines `localhost` de développement |

---

## 7. Intégration au reverse-proxy nginx

Une seule ligne a été ajoutée à la table de routage du gateway mutualisé,
`/root/iwm/ops/nginx/gateway.conf` :

```nginx
map $host $svc {
      default               "";
      "~^gandal\."          "gandal-api:8000";   # ← ajout GANDAL
      "~^api-caisse\."      "erp-cashier-backend:8081";
      "~^api\."             "iwm-app:8080";
      "~^verifid\."         "verifid-backend:8080";
      "~^caisse\."          "erp-cashier-frontend:3000";
}
```

- **Sauvegarde** : une copie horodatée `gateway.conf.bak.<timestamp>` a été créée avant
  modification.
- **Validation** : `docker exec iwm-gateway nginx -t` → *syntax is ok / test is successful*.
- **Application** : rechargement à chaud (`nginx -s reload`), **sans interruption** des
  autres services.
- **Non-régression** : un `Host` inconnu continue de renvoyer `404 Unknown host`,
  confirmant que les routes existantes restent intactes.

---

## 8. Sécurité et gestion des secrets

- Tous les secrets de production ont été **régénérés** (aucune valeur d'exemple
  `changeme123` / `change-me-*` conservée).
- Les secrets résident dans `/gandal-dev/.env` sur le serveur ; ce fichier **n'est pas
  versionné** (exclu par `.gitignore` et du transfert `rsync`).
- Le mot de passe administrateur a été communiqué **hors de ce document**.
- La base de données PostgreSQL n'est **pas exposée** sur l'hôte (port interne au
  réseau Docker uniquement).
- Le compte d'administration est protégé par une clé secrète (`SUPERADMIN_SECRET_KEY`)
  exigée à la création (`secrets.compare_digest`).

---

## 9. Recette — tests de validation

| # | Test | Commande / Endpoint | Résultat attendu | Statut |
|---|---|---|---|---|
| 1 | Démarrage base | `gandal-db` | `Up (healthy)` | ✅ |
| 2 | Migrations | `alembic upgrade head` | révisions `0001 → 0003` appliquées | ✅ |
| 3 | Démarrage API | `gandal-api` | `Application startup complete` | ✅ |
| 4 | Santé | `GET /health` | `{"status":"ok"}` | ✅ |
| 5 | Disponibilité DB | `GET /ready` | `{"status":"ready","database":true}` | ✅ |
| 6 | Routage gateway | `GET /health` (Host `gandal.*`) | `{"status":"ok"}` | ✅ |
| 7 | Non-régression | Host inconnu | `404 Unknown host` | ✅ |
| 8 | Documentation | `GET /docs` | `HTTP 200` (Swagger UI) | ✅ |
| 9 | Bootstrap admin | `POST /api/v1/auth/register-admin` | `HTTP 201` (compte créé) | ✅ |
| 10 | Authentification | `POST /api/v1/auth/login` | `HTTP 200` + jeton JWT | ✅ |
| 11 | Accès port direct | `http://10.50.30.102:8000/docs` | `HTTP 200` | ✅ |
| 12 | Accès via nip.io | `http://gandal.10.50.30.102.nip.io/docs` | `HTTP 200` | ✅ |

---

## 10. Accès à l'application

| Canal | URL | Usage |
|---|---|---|
| **Reverse-proxy (nominal)** | `http://gandal.10.50.30.102.nip.io/` | Production |
| Documentation interactive | `http://gandal.10.50.30.102.nip.io/docs` | Production |
| Port hôte direct | `http://10.50.30.102:8000/` | Diagnostic |

> **Résolution DNS.** Le serveur s'appuie sur le service wildcard **nip.io** : toute
> entrée `<préfixe>.10.50.30.102.nip.io` résout automatiquement vers `10.50.30.102`.
> Aucune configuration DNS supplémentaire n'est donc nécessaire. En cas de bascule
> ultérieure sur un nom de domaine réel, il suffira de pointer `gandal.<domaine>` (ou un
> enregistrement wildcard) vers `10.50.30.102`, sans modification côté serveur.

**Compte d'administration** : utilisateur `admin` (rôle `SuperAdmin`) — mot de passe
transmis séparément.

---

## 11. Exploitation et maintenance

Toutes les opérations s'effectuent depuis `/gandal-dev` :

```bash
ssh root@10.50.30.102
cd /gandal-dev

# État des services
docker compose -f docker-compose.prod.yml ps

# Journaux applicatifs (suivi)
docker compose -f docker-compose.prod.yml logs -f api

# Redémarrage
docker compose -f docker-compose.prod.yml restart api

# Mise à jour (après synchronisation d'une nouvelle version du code)
docker compose -f docker-compose.prod.yml up -d --build

# Arrêt / démarrage complet de la stack
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

**Sauvegarde de la base de données**
```bash
docker exec gandal-db pg_dump -U dc dc_backend > backup_$(date +%F).sql
```

---

## 12. Incidents rencontrés et résolutions

| Incident | Cause | Résolution |
|---|---|---|
| Coupures SSH intermittentes (« No route to host ») | Instabilité du lien réseau vers l'hôte | Encapsulation des commandes `ssh`/`scp` dans des boucles de réessai |
| Échec de `docker pull` (i/o timeout vers `registry-1.docker.io`) | Résolveur DNS du serveur (`10.50.30.1:53`) intermittent | Réutilisation de l'image `postgres:17-alpine` déjà présente ; build relancé en boucle de réessai |
| Première tentative : API non démarrée (`dependency db failed to start`) | Base pas encore `healthy` au premier essai | La boucle de réessai a relancé `up` ; succès au 2ᵉ essai une fois la base `healthy` |
| `register-admin` rejeté (`HTTP 422`) | Domaine e-mail `@dc.local` réservé, refusé par la validation `EmailStr` | Utilisation d'une adresse valide `admin@enspy-gi.cm` |
| Build long interrompu par coupure SSH | Lien réseau instable | Build exécuté **détaché** (`nohup`) côté serveur, survivant aux ruptures de session |

---

## 13. Risques résiduels et recommandations

| Priorité | Recommandation |
|---|---|
| 🔴 Haute | **Activer HTTPS/TLS** sur le gateway (certificat Let's Encrypt) — le trafic transite actuellement en clair sur le port 80. |
| 🟠 Moyenne | **Restreindre ou fermer le port 8000 direct** une fois la phase de diagnostic terminée (repasser le binding à `127.0.0.1:8000` ou le supprimer). |
| 🟠 Moyenne | **Affiner `CORS_ORIGINS`** avec l'origine réelle du frontend de production (actuellement limitée à des origines `localhost`). |
| 🟠 Moyenne | **Mettre en place une sauvegarde automatisée** du volume `gandal_pgdata` (cron `pg_dump` + externalisation). |
| 🟡 Basse | **Surveiller l'espace disque** (87 % utilisés) — purge régulière des images/volumes orphelins (`docker system prune`). |
| 🟡 Basse | **Stabiliser la résolution DNS** du serveur (résolveur secondaire fiable) pour fiabiliser les futurs `docker pull`. |
| 🟡 Basse | **Configurer le backend e-mail SMTP** si l'envoi de notifications réelles est requis (actuellement `EMAIL_BACKEND=log`). |
| 🟡 Basse | **Connecter Proxmox** (`PROXMOX_ENABLED=true` + identifiants) lorsque l'hyperviseur sera joignable — aujourd'hui en mode simulation. |

---

## 14. Annexes

**Fichiers livrés sur le serveur (`/gandal-dev/`)**
- Code applicatif (synchronisé depuis le dépôt)
- `docker-compose.prod.yml` — définition de la stack de production
- `.env` — variables d'environnement et secrets (non versionné)

**Fichier modifié sur le serveur**
- `/root/iwm/ops/nginx/gateway.conf` — ajout de la route `gandal.` (sauvegarde
  `gateway.conf.bak.<timestamp>` conservée)

**Références**
- Dépôt : `github.com/Delmat237/GANDAL-API`
- Documentation API (Swagger) : `/docs` — Redoc : `/redoc`
- Points de santé : `/health`, `/ready`

---

*Rapport établi le 11 juin 2026 — déploiement réalisé et validé.*
