"""Hash de senha (Argon2)."""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Gera hash Argon2 (com sal) — a senha em claro nunca é persistida."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Confere senha contra o hash em tempo constante."""
    return _password_hash.verify(password, password_hash)
