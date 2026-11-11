import subprocess
import re


def ping_host(host: str) -> int:
    if not re.match(r'^[a-zA-Z0-9.\-]+$', host):
        raise ValueError("Invalid host format")
    result = subprocess.run(["ping", "-c", "1", host], capture_output=True)
    return result.returncode
