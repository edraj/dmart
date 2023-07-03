#!/usr/bin/env python3

from utils.password_hashing import hash_password

print("Enter the password:")
password = input()

print(hash_password(password))
