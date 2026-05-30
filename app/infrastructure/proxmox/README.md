# Module d'Intégration Proxmox (dc-backend-negou-donald)

Ce dossier contient l'implémentation isolée de la logique de connexion et de provisionnement des Machines Virtuelles sur un cluster Proxmox. Il s'inspire du fonctionnement de l'application SIGMA Horizon.

## Contenu

*   **`config.py`** : Gestion de la configuration avec `pydantic-settings` (lecture du fichier `.env`).
*   **`proxmox_client.py`** : Le wrapper de l'API Proxmox utilisant la librairie `proxmoxer`. Gère la connexion par token et les appels HTTP.
*   **`service.py`** : La couche de service métier qui orchestre la création (résolution du VLAN, choix de la RAM, clonage et démarrage).
*   **`requirements.txt`** : Les dépendances Python nécessaires.
*   **`.env.example`** : Un exemple de variables d'environnement à définir.

## Comment utiliser ce module ?

### 1. Préparation de l'environnement
Créez un environnement virtuel et installez les dépendances :
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
Copiez le fichier `.env.example` en `.env` et remplissez-le avec les accès de votre Proxmox :
```bash
cp .env.example .env
```
Assurez-vous que l'utilisateur Proxmox possède un Token API valide (`PROXMOX_TOKEN_ID` et `PROXMOX_TOKEN_SECRET`).

### 3. Exécution d'un test
Vous pouvez utiliser le code suivant dans un script ou une console Python (`python -i service.py`) pour tester la création :

```python
from service import VMService

svc = VMService()

# Exemple de création (Assurez-vous d'avoir un Template Proxmox valide avec le VMID 9000 par exemple)
ssh_public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC..."
vm_info = svc.provision_new_vm(
    name="test-vm-api", 
    template_vmid=9000, 
    ram_gb=2.0, 
    vcpu=2, 
    ssh_pub_key=ssh_public_key, 
    vlan_id=105
)

print(vm_info)
```
