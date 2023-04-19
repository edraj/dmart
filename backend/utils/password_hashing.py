from hashlib import blake2b
from hmac import compare_digest
import bcrypt

#! TBD to add the salt
SECRET_KEY = b"pseudorandomly generated server secret key"
AUTH_SIZE = 32


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return (
        bcrypt_verify(plain_password, hashed_password) or 
        hmac_verify(plain_password, hashed_password)
    )


def bcrypt_verify(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except :
        return False


def hmac_verify(plain_password: str, hashed_password: str) -> bool:
    try:
        return compare_digest(hmac_hash(plain_password), hashed_password)
    except :
        return False


def hash_password(password: str) -> str:
    bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(bytes, salt)

def hmac_hash(password: str) -> str:
    h = blake2b(digest_size=AUTH_SIZE, key=SECRET_KEY)
    h.update(bytes(password, "utf-8"))
    return h.hexdigest()