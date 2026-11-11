class UserService:
    def __init__(self):
        self.users = {1: "alice", 2: "bob"}
        self.admins = {1}

    def get_current_user(self, session_token: str):
        # Simplified: always returns user_id=1
        return 1

    def delete_user_account(self, session_token: str, target_user_id: int) -> bool:
        current_user_id = self.get_current_user(session_token)
        if current_user_id != target_user_id and current_user_id not in self.admins:
            raise PermissionError("Not authorized to delete this account")
        if target_user_id in self.users:
            del self.users[target_user_id]
            return True
        return False
