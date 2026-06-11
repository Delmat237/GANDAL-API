import ipaddress


def pick_guest_ipv4(interfaces: list[dict]) -> str | None:
    """Extrait la première IPv4 utilisable depuis la réponse qemu-guest-agent."""
    for iface in interfaces:
        for addr in iface.get("ip-addresses") or []:
            if addr.get("ip-address-type") != "ipv4":
                continue
            raw = addr.get("ip-address")
            if not raw:
                continue
            try:
                parsed = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if parsed.is_loopback or parsed.is_link_local:
                continue
            return str(parsed)
    return None
