from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import shutil
import subprocess
from typing import Iterator, Literal
import postgresql_binaries
import psycopg

SUPERUSER = "postgres"


def initdb(
    directory: Path,
    *,
    on_existing: Literal["raise", "use", "clear"] = "raise",
) -> None:
    """Call `initdb` with some sensible arguments."""
    if directory.exists():
        if on_existing == "raise":
            raise RuntimeError(f"Directory {directory} already exists")
        if on_existing == "clear":
            shutil.rmtree(directory)
        if on_existing == "use":
            return

    directory.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [
        str(postgresql_binaries.bin() / "initdb"),
        *("-D", str(directory)),
        *("--username", SUPERUSER),
        *("--auth-host", "trust"),
        "--no-sync",
    ]
    subprocess.check_call(cmd)


@dataclass(kw_only=True)
class PostgresqlConfig:
    user: str
    password: str
    host: str
    port: int
    database: str
    stderr: Path
    directory: Path
    dsn: str = ""

    def __post_init__(self) -> None:
        self.dsn = f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @staticmethod
    def default(name: str) -> "PostgresqlConfig":
        ROOT = Path(".postgresql_testing")
        DATABASES = ROOT / "databases"
        LOGS = ROOT / "logs"
        return PostgresqlConfig(
            user=name,
            password="",
            host="localhost",
            port=8421,
            database=name,
            stderr=LOGS / f"{name}.log",
            directory=DATABASES / name,
        )

    def superuser(self) -> PostgresqlConfig:
        return replace(
            self,
            user=SUPERUSER,
            database="postgres",
        )


@contextmanager
def server(config: PostgresqlConfig) -> Iterator[None]:
    """Call `postgres` with some sensible arguments."""
    config.stderr.parent.mkdir(parents=True, exist_ok=True)
    with open(config.stderr, "w") as stderr_f:
        cmd = [
            str(postgresql_binaries.bin() / "postgres"),
            *("-D", str(config.directory)),
            *("-h", str(config.host)),
            *("-p", str(config.port)),
            *("-c", "fsync=off"),  # turn off fsync for speed
            *("-c", "log_statement=all"),
        ]
        process = subprocess.Popen(cmd, stderr=stderr_f)
        try:
            _try_connect(config.superuser().dsn)
            with psycopg.connect(config.superuser().dsn) as conn:
                conn.autocommit = True
                user_exists = bool(conn.execute(f"SELECT 1 FROM pg_roles WHERE rolname = '{config.user}'").fetchall())
                db_exists = bool(conn.execute(f"SELECT 1 FROM pg_database WHERE datname = '{config.database}'").fetchall())
                if not user_exists:
                    conn.execute(f"CREATE ROLE {config.user} LOGIN PASSWORD '{config.password}'")
                if not db_exists:
                    conn.execute(f"CREATE DATABASE {config.database} OWNER {config.user}")
            yield
        finally:
            process.terminate()


def _try_connect(dsn: str) -> None:
    for _ in range(100):
        try:
            with psycopg.connect(dsn) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError:
            pass
    raise RuntimeError(f"Could not connect to {dsn}")
