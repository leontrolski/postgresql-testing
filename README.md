# Postgresql testing

Simple Postgres helpers for testing with Python - no docker, brew, apt, etc - uses [postgresql-binaries](https://github.com/leontrolski/postgresql-binaries).

```shell
pip install postgresql-testing 'postgresql-binaries==18.*'
```

Then to use, eg:

```python
import postgresql_testing

@pytest.fixture(scope="session")
def db() -> Iterator[str]:
    config = postgresql_testing.DatabaseConfig.default("testing-db")
    postgresql_testing.initdb(config.directory, on_existing="use")
    with postgresql_testing.serve(config):
        postgresql_testing.ensure_user(config)
        postgresql_testing.create_database(config, on_existing="replace")
        yield config.dsn
```

There are various useful flags and things - the source code is short enough to just dive in.

<hr>

There are a couple of helpers for creating/using template dbs and tar files. I have some vague long term plan for some kind of "Docker layers for migrated databases" with clever caching, but I'm not quite sure what it looks like yet.
