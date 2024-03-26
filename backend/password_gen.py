#!/usr/bin/env python3

from utils.password_hashing import hash_password

print("Enter the password: ", end="")
password = input()
print("Generated hash: ", end="")
print(hash_password(password))
