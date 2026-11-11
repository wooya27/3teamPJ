import pathlib

BASE_DIR = pathlib.Path("/var/userfiles")


def read_user_file(filename: str) -> str:
    file_path = (BASE_DIR / filename).resolve()
    if not str(file_path).startswith(str(BASE_DIR.resolve())):
        raise ValueError("Access denied: path traversal detected")
    return file_path.read_text()
