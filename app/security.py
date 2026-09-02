import hashlib
import hmac
import secrets

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 220_000)
    return salt.hex() + ":" + digest.hex()

def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, digest_hex = encoded.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 220_000)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

def is_authenticated(request) -> bool:
    return bool(request.session.get("user"))
