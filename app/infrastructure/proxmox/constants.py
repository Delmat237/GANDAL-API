OS_TEMPLATES: dict[str, int] = {
    "Ubuntu 22.04": 9000,
    "Debian 12": 9001,
}

DEPARTMENT_VLAN_MAP: dict[str, int] = {
    "Computer Science": 105,
    "default": 100,
}


def resolve_vlan_for_department(departement: str) -> int:
    return DEPARTMENT_VLAN_MAP.get(departement, DEPARTMENT_VLAN_MAP["default"])


def resolve_template_for_os(os_name: str) -> int:
    if os_name not in OS_TEMPLATES:
        raise ValueError(f"OS non supporté: {os_name}")
    return OS_TEMPLATES[os_name]
