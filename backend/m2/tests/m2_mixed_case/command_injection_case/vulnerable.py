import os


def ping_host(host: str) -> int:
    return os.system(f"ping -c 1 {host}")
