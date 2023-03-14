from hashlib import blake2b
from hmac import compare_digest

#! TBD to add the salt
SECRET_KEY = b"pseudorandomly generated server secret key"
AUTH_SIZE = 32


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return compare_digest(hash_password(plain_password), hashed_password)
    # return hash_password(plain_password) == hashed_password


def hash_password(password: str) -> str:
    h = blake2b(digest_size=AUTH_SIZE, key=SECRET_KEY)
    h.update(bytes(password, "utf-8"))
    return h.hexdigest()
