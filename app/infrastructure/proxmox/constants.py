# Templates présents sur le nœud emilia (cluster Proxmox de prod).
# 2299 = omega-cloud-template (cloud-init), 9001 = omega-template-base.
OS_TEMPLATES: dict[str, int] = {
    "Ubuntu 22.04": 2299,
    "Debian 12": 9001,
}

DEPARTMENT_VLAN_MAP: dict[str, int] = {
    "Computer Science": 105,
    "default": 100,
}


def resolve_vlan_for_department(departement: str) -> int:
    return DEPARTMENT_VLAN_MAP.get(departement, DEPARTMENT_VLAN_MAP["default"])


def resolve_template_for_os(os_name: str) -> int:
    if not isinstance(os_name, str):
        supported_os = ", ".join(OS_TEMPLATES.keys())
        raise ValueError(f"OS non supporté: {os_name}. Les OS supportés sont : {supported_os}")

    # Normalisation : minuscules, suppression des espaces en début/fin et
    # réduction des espaces multiples internes à un seul espace.
    normalized = " ".join(os_name.lower().split())

    # Mapping des alias
    if normalized in ("ubuntu", "ubuntu 22.04"):
        return OS_TEMPLATES["Ubuntu 22.04"]
    elif normalized in ("debian", "debian 12"):
        return OS_TEMPLATES["Debian 12"]

    supported_os = ", ".join(OS_TEMPLATES.keys())
    raise ValueError(f"OS non supporté: {os_name}. Les OS supportés sont : {supported_os}")

