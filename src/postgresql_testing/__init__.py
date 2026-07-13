from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import shutil
import subprocess
from typing import Iterator, Literal, Self
import postgresql_binaries
import psycopg
import tarfile

DEFAULT_DIR = Path("/tmp/.postgresql_testing")
SUPERUSER = "postgres"
ROOT_DATABASE = "postgres"


@dataclass(kw_only=True)
class ClusterConfig:
    host: str
    port: int
    stderr: Path
    directory: Path

    def superuser(self) -> DatabaseConfig:
        return DatabaseConfig(
            user=SUPERUSER,
            password="",
            database=ROOT_DATABASE,
            host=self.host,
            port=self.port,
            stderr=self.stderr,
            directory=self.directory,
        )


@dataclass(kw_only=True)
class DatabaseConfig(ClusterConfig):
    user: str
    password: str
    database: str
    dsn: str = ""

    def __post_init__(self) -> None:
        self.dsn = f"postgres://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def default(
        cls,
        database: str,
        *,
        user: str = "testing",
        password: str = "",
        port: int = 8421,
        directory: Path = DEFAULT_DIR / "database",
    ) -> Self:
        logs = directory.parent / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        return cls(
            user=user,
            password=password,
            host="localhost",
            port=port,
            database=database,
            stderr=logs / f"{database}.log",
            directory=directory,
        )


def initdb(
    directory: Path,
    *,
    on_existing: Literal["raise", "use", "replace"] = "raise",
) -> None:
    """Call `initdb` with some sensible arguments for testing."""
    if directory.exists():
        if on_existing == "raise":
            raise RuntimeError(f"Directory {directory} already exists")
        if on_existing == "replace":
            shutil.rmtree(directory)
        if on_existing == "use":
            return

    directory.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [
        str(postgresql_binaries.bin() / "initdb"),
        *("-D", str(directory)),
        *("--username", SUPERUSER),
        *("--auth-host", "trust"),
        *("--wal-segsize", "1"),
        "--no-sync",
        "--no-instructions",
    ]
    subprocess.check_call(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@contextmanager
def serve(c: ClusterConfig) -> Iterator[None]:
    """Call `postgres` with some sensible arguments."""
    c.stderr.parent.mkdir(parents=True, exist_ok=True)
    with open(c.stderr, "wb") as stderr_f:
        cmd = [
            str(postgresql_binaries.bin() / "postgres"),
            *("-D", str(c.directory)),
            *("-h", str(c.host)),
            *("-p", str(c.port)),
            *("-c", "fsync=off"),
            *("-c", "synchronous_commit=off"),
            *("-c", "full_page_writes=off"),
            # *("-c", "wal_level=minimal"),
            # *("-c", "log_statement=all"),
        ]
        process = subprocess.Popen(cmd, stderr=stderr_f)
        try:
            _try_connect(c.superuser().dsn)
            yield
        finally:
            process.terminate()
            process.wait()


@contextmanager
def create_template(
    c: DatabaseConfig,
    *,
    template: str,
    on_existing: Literal["raise", "replace"] = "replace",
) -> Iterator[DatabaseConfig]:
    with psycopg.connect(c.superuser().dsn) as conn, conn.cursor() as cur:
        conn.autocommit = True
        template_exists = bool(cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{template}'").fetchall())
        if template_exists:
            if on_existing == "raise":
                raise RuntimeError(f"Template database {template} already exists")
            if on_existing == "replace":
                cur.execute(f"UPDATE pg_database SET datistemplate = false WHERE datname='{template}'")
                cur.execute(f'DROP DATABASE "{template}"')

        cur.execute(f'CREATE DATABASE "{template}" OWNER "{c.user}"')
        yield replace(c, database=template)
        cur.execute(f"UPDATE pg_database SET datistemplate = true WHERE datname='{template}'")


def ensure_user(c: DatabaseConfig) -> None:
    with psycopg.connect(c.superuser().dsn) as conn, conn.cursor() as cur:
        try:
            cur.execute(f"CREATE ROLE \"{c.user}\" LOGIN PASSWORD '{c.password}'")
        except psycopg.errors.DuplicateObject:
            pass


def create_database(
    c: DatabaseConfig,
    *,
    template: str | None = None,
    on_existing: Literal["raise", "replace"] = "replace",
) -> None:
    """Create a Postgres database.

    - Optionally pass in a template.
    - Takes in the tens of ms for a small db.
    """
    template_str = "" if template is None else f'WITH TEMPLATE "{template}"'
    sql_create_database = f'CREATE DATABASE "{c.database}" {template_str} OWNER "{c.user}" STRATEGY=FILE_COPY'

    with psycopg.connect(c.superuser().dsn) as conn, conn.cursor() as cur:
        conn.autocommit = True
        try:
            cur.execute(sql_create_database)
        except psycopg.errors.DuplicateDatabase:
            if on_existing == "raise":
                raise RuntimeError(f"Database {c.database} already exists")
            if on_existing == "replace":
                cur.execute(f'DROP DATABASE "{c.database}"')
                cur.execute(sql_create_database)


def dump_archive(
    directory: Path,
    archive: Path,
    *,
    on_existing: Literal["raise", "replace"] = "replace",
) -> None:
    """Dump the entirety of a Postgres cluster to a tar archive.

    - Archives are not very portable (between system architectures or Postgres
      versions).
    - Takes in the hundreds of ms for a small db.
    """
    if archive.exists():
        if on_existing == "raise":
            raise RuntimeError(f"Archive {archive} already exists")
        archive.unlink()

    with tarfile.open(archive, "w") as tar:
        tar.add(directory, arcname=directory.name)


def load_archive(
    archive: Path,
    directory: Path,
    *,
    on_existing: Literal["raise", "replace"] = "replace",
) -> None:
    """Dump the entirety of a Postgres cluster from a tar archive."""
    if directory.exists():
        if on_existing == "raise":
            raise RuntimeError(f"Directory {directory} already exists")
        shutil.rmtree(directory)

    with tarfile.open(archive) as tar:
        tar.extractall(directory.parent)


def _try_connect(dsn: str) -> None:
    for _ in range(500):
        try:
            with psycopg.connect(dsn) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError:
            pass
    raise RuntimeError(f"Could not connect to {dsn}")
