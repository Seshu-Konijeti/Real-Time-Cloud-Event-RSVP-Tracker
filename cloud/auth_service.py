"""Auth helpers. Swap this module for Firebase Auth / Supabase / Cognito in the cloud build."""
from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(pw):
    return generate_password_hash(pw)


def verify_password(pw_hash, pw):
    return check_password_hash(pw_hash, pw)
