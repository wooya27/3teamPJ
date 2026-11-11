import os
import hashlib


class FakeDatabase:
    def query(self, sql):
        return f"[DB] Executing: {sql}"


db = FakeDatabase()


def login(username: str, password: str):
    hashed = hashlib.md5(password.encode()).hexdigest()
    sql = f"SELECT * FROM users WHERE name = '{username}' AND pw = '{hashed}'"
    return db.query(sql)


def write_audit_log(message: str) -> int:
    return os.system(f"echo {message} >> /var/log/audit.log")
