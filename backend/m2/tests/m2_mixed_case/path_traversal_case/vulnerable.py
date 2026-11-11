import pathlib

BASE_DIR = pathlib.Path("/var/userfiles")


def read_user_file(filename: str) -> str:
    file_path = BASE_DIR / filename
    return file_path.read_text()
