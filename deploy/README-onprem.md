# Déploiement on-premise — Console GANDAL/Omega

Trois services, tous sur le **contrôleur du cluster (emilia, 192.168.123.100)** :

| Service | Rôle | Port | Repo |
|---|---|---|---|
| `gandal-api` | API de contrôle (VMs, réseau, distribution, auth) | 8080 | `GANDAL-API` |
| `gandal-ai` | Assistant IA du chatbot (RAG) | 8090 | `gandal-ai` |
| front Next.js | Interface utilisateur/admin | 3000 | `Gandal` |

Le backend doit tourner **sur un nœud PVE** pour piloter `pvesh`/`qm` en local et exécuter
les scripts `omega-remote-paging` (présents dans `/opt/omega-remote-paging`, déployés via
`make deploy-deb`).

## 1. Backend GANDAL-API
```bash
sudo mkdir -p /opt/gandal && cd /opt/gandal
git clone <fork>/GANDAL-API && cd GANDAL-API
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.omega.example .env       # éditer les secrets + PROXMOX_BACKEND=omega
# tables : alembic upgrade head   (ou create_all au 1er démarrage pour SQLite)
sudo cp deploy/gandal-api.service /etc/systemd/system/
sudo systemctl enable --now gandal-api
# créer le superadmin : POST /api/v1/auth/register-admin (role=SuperAdmin + secret_key)
```
Vérifier : `curl http://localhost:8080/health` puis `GET /api/v1/cluster/topology` (avec token).

**Pré-requis distribution** : pour que `/cluster/distribution` réponde, le réconciliateur
doit être dans `/opt` → lancer `make deploy-deb` depuis `omega-remote-paging` (pousse aussi
le fix de placement 1/2/2 et `omega-distribution-reconciler.sh`).

## 2. Service IA gandal-ai
```bash
cd /opt/gandal && git clone <fork>/gandal-ai && cd gandal-ai
python3 -m venv .venv && . .venv/bin/activate
pip install -r service/requirements.txt        # mode extractif (offline)
sudo cp deploy/gandal-ai.service /etc/systemd/system/
sudo systemctl enable --now gandal-ai
```
Backend LLM optionnel : exporter `GANDAL_LLM_BACKEND=ollama` (+ `GANDAL_OLLAMA_URL`,
`GANDAL_LLM_MODEL`) ou `transformers`. Par défaut = RAG extractif, sans modèle.

## 3. Front Next.js
```bash
cd /opt/gandal && git clone <fork>/Gandal && cd Gandal
npm ci
cp .env.example .env.local       # NEXT_PUBLIC_API_BASE + NEXT_PUBLIC_CHAT_API_BASE
npm run build
npx next start -H 0.0.0.0 -p 3000   # ou un service systemd équivalent
```

## Accès & sécurité
- Exposer le front derrière pfSense ; restreindre 8080/8090 au LAN/au front.
- DNS : la console peut être publiée en `gandal.enspy-gi.gandal` (pfSense Unbound).
- Rôles : étudiant (ses VMs), enseignant (approbation), superadmin (cluster complet).
