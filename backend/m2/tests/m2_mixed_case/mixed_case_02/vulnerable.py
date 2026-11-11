import os
import pathlib

BASE_DIR = pathlib.Path("/var/userfiles")


class AdminService:
    def __init__(self):
        self.users = {1: "alice", 2: "bob"}

    def get_current_user(self, session_token: str):
        # Simplified: always returns user_id=1
        return 1

    def read_user_file(self, filename: str) -> str:
        file_path = BASE_DIR / filename
        return file_path.read_text()

    def run_diagnostic(self, host: str) -> int:
        return os.system(f"ping -c 1 {host}")

    def delete_user_account(self, session_token: str, target_user_id: int) -> bool:
        current_user_id = self.get_current_user(session_token)
        if target_user_id in self.users:
            del self.users[target_user_id]
            return True
        return False
