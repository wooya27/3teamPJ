DATABASE_URL = "postgresql://admin:supersecret123@prod-db.internal/appdb"
JWT_SECRET = "my-hardcoded-jwt-secret-key"


def get_db_url() -> str:
    return DATABASE_URL


def get_jwt_secret() -> str:
    return JWT_SECRET
