"""Destructive to CONTAINERS only: run on a dedicated Compose test project.

Keeps volumes. Uses synthetic bytes and removes its marker after verification.
Usage: python scripts/verify_infrastructure.py --env-file /tmp/test.env --project test-name
"""

import argparse
import json
import subprocess
import time
from uuid import uuid4

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--env-file", required=True)
parser.add_argument("--project", required=True)
args = parser.parse_args()
compose = ["docker", "compose", "--env-file", args.env_file, "-p", args.project]


def run(*command, input=None):
    result = subprocess.run(
        compose + list(command),
        input=input,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr + result.stdout)
    return result.stdout


def python(service, code):
    return run("exec", "-T", service, "python", "-", input=code).strip()


def wait_ready():
    for attempt in range(60):
        try:
            python(
                "api",
                "import urllib.request; urllib.request.urlopen('http://localhost:8010/ready/upload', timeout=5)",
            )
            return
        except RuntimeError:
            time.sleep(1)
    raise RuntimeError("API did not become ready")


for service in ("migrate", "storage-init", "bootstrap"):
    for _ in range(2):
        run("run", "--rm", service)
print(
    "S01-02/S01-08: repeated migration/bootstrap/bucket initialization OK", flush=True
)
wait_ready()
marker = str(uuid4())
key = f"spec01-persistence/{marker}.ogg"
common = """
from call_summary.db.session import get_engine
from call_summary.storage import S3Storage
from sqlalchemy import text
storage = S3Storage()
"""
python(
    "api",
    common
    + f"""
with get_engine().begin() as conn:
    conn.execute(text('INSERT INTO call_summary.workspaces (id,name) VALUES (:id,:name)'), dict(id={marker!r}, name='spec01 persistence'))
assert storage.put({key!r}, b'spec01 synthetic persistence')
""",
)
read_marker = (
    common
    + f"""
with get_engine().connect() as conn:
    assert conn.scalar(text('SELECT name FROM call_summary.workspaces WHERE id=:id'), dict(id={marker!r})) == 'spec01 persistence'
assert storage.get({key!r}) == b'spec01 synthetic persistence'
"""
)
for service in ("api", "worker"):
    python(service, read_marker)
config = json.loads(run("config", "--format", "json"))
for service in ("api", "worker"):
    assert not config["services"][service].get("volumes")
    env = config["services"][service]["environment"]
    assert (
        not {"MINIO_ROOT_PASSWORD", "POSTGRES_PASSWORD", "MIGRATION_DATABASE_URL"}
        & env.keys()
    )
print(
    "S01-07/S01-09: both processes read S3; no shared volumes/admin credentials",
    flush=True,
)
run("down")
run("up", "-d")
wait_ready()
for service in ("api", "worker"):
    python(service, read_marker)
print("S01-06: database row and S3 bytes survived container recreation", flush=True)
run("stop", "minio")
try:
    python(
        "api",
        """
from urllib.request import urlopen
from urllib.error import HTTPError
assert urlopen('http://localhost:8010/ready/read', timeout=10).status == 200
try:
    urlopen('http://localhost:8010/ready/upload', timeout=30)
except HTTPError as error:
    assert error.code == 503
else:
    raise AssertionError('upload readiness accepted unavailable MinIO')
""",
    )
    print(
        "S01-09: with MinIO stopped, read readiness=200, upload readiness=503",
        flush=True,
    )
finally:
    run("start", "minio")
wait_ready()
python(
    "api",
    common
    + f"""
storage.delete({key!r})
with get_engine().begin() as conn:
    conn.execute(text('DELETE FROM call_summary.workspaces WHERE id=:id'), dict(id={marker!r}))
""",
)
print(
    "Lifecycle verification passed; project left running, volumes retained", flush=True
)
