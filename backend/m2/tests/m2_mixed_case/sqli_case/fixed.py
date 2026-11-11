class FakeDatabase:
    def query(self, sql, params=None):
        return f"[DB] Executing: {sql} with params={params}"


db = FakeDatabase()


def get_user_by_name(username: str):
    sql = "SELECT * FROM users WHERE name = ?"
    return db.query(sql, params=(username,))
