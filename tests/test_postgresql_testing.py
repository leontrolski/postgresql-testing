import time

import postgresql_testing
import psycopg


def test_connection() -> None:
    config = postgresql_testing.DatabaseConfig.default("yoho")
    postgresql_testing.initdb(config.directory, on_existing="use")
    with postgresql_testing.serve(config):
        postgresql_testing.ensure_user(config)
        postgresql_testing.create_database(config)
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT 1").fetchall()


def test_templates() -> None:
    config = postgresql_testing.DatabaseConfig.default("testing-db")
    postgresql_testing.initdb(config.directory, on_existing="replace")
    with postgresql_testing.serve(config):
        postgresql_testing.ensure_user(config)
        with postgresql_testing.create_template(config, template="migration_state_x") as c:
            with psycopg.connect(c.dsn) as conn:
                conn.execute("CREATE TABLE x (a INT)")
                conn.execute("INSERT INTO x VALUES (1)")

        postgresql_testing.create_database(config, template="migration_state_x")
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]

    with postgresql_testing.serve(config):
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]

    config = postgresql_testing.DatabaseConfig.default("ahoy")
    with postgresql_testing.serve(config):
        postgresql_testing.create_database(config, template="migration_state_x")
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]


def test_archive() -> None:
    archive = postgresql_testing.DEFAULT_DIR / "oioi.tar"

    config = postgresql_testing.DatabaseConfig.default("oioi", directory=postgresql_testing.DEFAULT_DIR / "oioi")
    postgresql_testing.initdb(config.directory, on_existing="replace")
    with postgresql_testing.serve(config):
        postgresql_testing.ensure_user(config)
        postgresql_testing.create_database(config)
        with psycopg.connect(config.dsn) as conn:
            conn.execute("CREATE TABLE x (a INT)")
            conn.execute("INSERT INTO x VALUES (1)")
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]
        postgresql_testing.dump_archive(config, archive)

    with postgresql_testing.serve(config):
        postgresql_testing.load_archive(archive, config)
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]

    with postgresql_testing.serve(config):
        postgresql_testing.load_archive(archive, config)
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]


def test_benchmark() -> None:
    print()

    config = postgresql_testing.DatabaseConfig.default("yoho")
    postgresql_testing.initdb(config.directory, on_existing="use")
    archive = postgresql_testing.DEFAULT_DIR / "yoho.tar"
    for n in [100, 1000]:
        with postgresql_testing.serve(config):
            postgresql_testing.ensure_user(config)
            with postgresql_testing.create_template(config, template="migration_state_x") as c:
                with psycopg.connect(c.dsn) as conn:
                    for i in range(n):
                        conn.execute(f"CREATE TABLE t_{i} (a INT, b TEXT, c JSONB)")
                        conn.execute(f"CREATE INDEX i_{i} ON t_{i} (a, b)")

            before = time.time()
            postgresql_testing.create_database(config, template="migration_state_x")
            print(f"Creating {n}-table db from template took: {(time.time() - before) * 1000:.0f}ms")

            before = time.time()
            postgresql_testing.dump_archive(config, archive)
            print(
                f"Dumping {n}-table db to archive ({_pretty_size(archive.stat().st_size)}) took: {(time.time() - before) * 1000:.0f}ms"
            )

            before = time.time()
            postgresql_testing.load_archive(archive, config)
            print(f"Loading {n}-table db to archive took: {(time.time() - before) * 1000:.0f}ms")


def _pretty_size(num_bytes: int) -> str:
    units = iter(["B", "KB", "MB", "GB", "TB", "PB"])
    unit = next(units)
    size = float(num_bytes)

    while size >= 1024:
        size /= 1024
        unit = next(units)

    return f"{size:.1f} {unit}"
