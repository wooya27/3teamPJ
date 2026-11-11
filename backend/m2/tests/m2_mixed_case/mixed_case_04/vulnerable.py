import os
import pathlib

BACKUP_DIR = pathlib.Path("/var/backups")
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


def archive_path(filename: str) -> str:
    target = BACKUP_DIR / filename
    return target.read_text()


def compress_backup(name: str) -> int:
    return os.system(f"tar -czf /tmp/{name}.tar.gz /var/backups/{name}")
