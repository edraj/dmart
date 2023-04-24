import bcrypt

#! TBD to add the salt
SECRET_KEY = b"pseudorandomly generated server secret key"
AUTH_SIZE = 32


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except :
        return False


def hash_password(password: str) -> str:
    bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(bytes, salt).decode("ascii")
