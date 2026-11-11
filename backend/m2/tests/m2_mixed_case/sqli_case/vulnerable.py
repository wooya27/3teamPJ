class FakeDatabase:
    def query(self, sql):
        return f"[DB] Executing: {sql}"


db = FakeDatabase()


def get_user_by_name(username: str):
    sql = f"SELECT * FROM users WHERE name = '{username}'"
    return db.query(sql)
