import hashlib


JWT_SECRET = "my-hardcoded-jwt-secret-key"


class FakeDatabase:
    def query(self, sql):
        return f"[DB] Executing: {sql}"


db = FakeDatabase()


class AccountService:
    def __init__(self):
        self.users = {1: "alice", 2: "bob"}

    def get_current_user(self, session_token: str):
        # Simplified: always returns user_id=1
        return 1

    def find_user(self, username: str):
        sql = f"SELECT * FROM users WHERE name = '{username}'"
        return db.query(sql)

    def set_password(self, user_id: int, password: str) -> str:
        return hashlib.md5(password.encode()).hexdigest()

    def delete_user_account(self, session_token: str, target_user_id: int) -> bool:
        current_user_id = self.get_current_user(session_token)
        if target_user_id in self.users:
            del self.users[target_user_id]
            return True
        return False
