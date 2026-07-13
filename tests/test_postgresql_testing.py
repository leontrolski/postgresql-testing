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
    config = postgresql_testing.DatabaseConfig.default("oioi", directory=postgresql_testing.DEFAULT_DIR / "oioi")
    postgresql_testing.initdb(config.directory, on_existing="replace")
    with postgresql_testing.serve(config):
        postgresql_testing.ensure_user(config)
        postgresql_testing.create_database(config)
        with psycopg.connect(config.dsn) as conn:
            conn.execute("CREATE TABLE x (a INT)")
            conn.execute("INSERT INTO x VALUES (1)")
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]

    archive = postgresql_testing.DEFAULT_DIR / "oioi.tar"

    postgresql_testing.dump_archive(config.directory, archive)

    postgresql_testing.load_archive(archive, config.directory)

    with postgresql_testing.serve(config):
        with psycopg.connect(config.dsn) as conn:
            assert conn.execute("SELECT * FROM x").fetchall() == [(1,)]
