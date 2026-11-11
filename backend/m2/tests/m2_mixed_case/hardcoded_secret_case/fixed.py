import os


DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]


def get_db_url() -> str:
    return DATABASE_URL


def get_jwt_secret() -> str:
    return JWT_SECRET
