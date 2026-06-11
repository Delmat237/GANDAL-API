from app.infrastructure.proxmox.ip_utils import pick_guest_ipv4


def test_pick_guest_ipv4_skips_loopback_and_link_local():
    interfaces = [
        {
            "name": "lo",
            "ip-addresses": [
                {"ip-address": "127.0.0.1", "ip-address-type": "ipv4"},
            ],
        },
        {
            "name": "eth0",
            "ip-addresses": [
                {"ip-address": "169.254.1.1", "ip-address-type": "ipv4"},
                {"ip-address": "10.50.30.55", "ip-address-type": "ipv4"},
            ],
        },
    ]
    assert pick_guest_ipv4(interfaces) == "10.50.30.55"


def test_pick_guest_ipv4_returns_none_when_empty():
    assert pick_guest_ipv4([]) is None
