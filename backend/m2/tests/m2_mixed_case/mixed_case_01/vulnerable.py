import hashlib


DATABASE_URL = "postgresql://admin:supersecret123@prod-db.internal/appdb"
API_KEY = "sk-live-9f8b7c6d5e4f3a2b1c0d"


class FakeDatabase:
    def query(self, sql):
        return f"[DB] Executing: {sql}"


db = FakeDatabase()


def authenticate(username: str, password: str):
    hashed = hashlib.md5(password.encode()).hexdigest()
    sql = f"SELECT * FROM users WHERE name = '{username}' AND pw = '{hashed}'"
    return db.query(sql)
