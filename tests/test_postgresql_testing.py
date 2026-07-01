import postgresql_testing
import psycopg


def test_connection() -> None:
    config = postgresql_testing.PostgresqlConfig.default("yoho")
    postgresql_testing.initdb(config.directory, on_existing="clear")
    with postgresql_testing.server(config):
        with psycopg.connect(config.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                print(cur.fetchall())
