from argon2 import PasswordHasher

ph = PasswordHasher(
    memory_cost=102400,
    time_cost=1,
    parallelism=8
)

def verify_password(plain_password: str, hashed_password: str):
    try:
        return ph.verify(hashed_password, plain_password)
    except Exception:
        return False

def hash_password(password: str):
    return ph.hash(password)
