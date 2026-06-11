from app.infrastructure.proxmox.ssh_keys import (
    generate_ssh_key_pair,
    is_valid_ssh_public_key,
    resolve_ssh_public_key,
)


def test_is_valid_ssh_public_key_rejects_mock_and_empty():
    assert not is_valid_ssh_public_key("")
    assert not is_valid_ssh_public_key("ssh-rsa mock")
    assert not is_valid_ssh_public_key("ssh-rsa AAAAB3")
    assert not is_valid_ssh_public_key(None)


def test_generate_ssh_key_pair_produces_valid_openssh():
    public_key, private_key = generate_ssh_key_pair()
    assert public_key.startswith("ssh-ed25519 ")
    assert is_valid_ssh_public_key(public_key)
    assert "OPENSSH PRIVATE KEY" in private_key


def test_resolve_ssh_public_key_keeps_valid_input():
    public_key, _ = generate_ssh_key_pair()
    resolved = resolve_ssh_public_key(public_key)
    assert resolved.public_key == public_key
    assert resolved.private_key is None
    assert not resolved.was_generated


def test_resolve_ssh_public_key_generates_when_invalid():
    resolved = resolve_ssh_public_key("ssh-rsa mock")
    assert resolved.was_generated
    assert resolved.private_key is not None
    assert is_valid_ssh_public_key(resolved.public_key)
