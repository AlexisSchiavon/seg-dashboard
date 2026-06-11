from app.auth.security import get_password_hash, verify_password


def test_password_hash_roundtrip():
    plain = "correct horse battery staple"
    hashed = get_password_hash(plain)

    assert verify_password(plain, hashed) is True
    assert verify_password("wrong password", hashed) is False
