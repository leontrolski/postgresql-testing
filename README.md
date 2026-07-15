# Postgresql testing

Simple Postgres helpers for testing with Python - no docker, brew, apt, etc - uses [postgresql-binaries](https://github.com/leontrolski/postgresql-binaries). The interface is simple, but close enough to the metal that you can use it to eg. have a new database per testing thread/use a fresh database from a `TEMPLATE` or archive.

```shell
pip install postgresql-testing 'postgresql-binaries==18.*'
```

Then to use with pytest, eg:

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

<hr id="postgresql-testing-serve">

You can spin up a fresh db for immediate testing with:

```bash
postgresql-testing-serve postgres://testing:@localhost:8421/my-db
```

<hr id="postgresql-testing-explain">

Bundled for good measure is a local-first copy of [explain.dalibo.com](https://explain.dalibo.com/).

Get your query plan by:

```sql
EXPLAIN (ANALYZE, COSTS, VERBOSE, BUFFERS, FORMAT JSON) SELECT ...
```

Then copy and:

```bash
pbpaste | postgresql-testing-explain
```

<hr>

There are a couple of helpers for creating/using template dbs and archives. I have some vague long term plan for some kind of "Docker layers for migrated databases" with clever caching (or not), but I'm not quite sure what it looks like yet.

Some benchmarking:

| number of tables | create from template | dump to archive | create from archive |
|---|---|---|---|
| 100 | 80ms | 80ms (0.2MB) | 150ms |
| 1000 | 500ms | 300ms (2MB) | 1100ms |

On macos using a ramdisk, it is slightly quicker:

| number of tables | create from template | dump to archive | create from archive |
|---|---|---|---|
| 100 | 70ms | 70ms | 120ms |
| 1000 | 350ms | 300ms | 1000ms |

See claims/advice from planet [Go](https://github.com/peterldowns/pgtestdb).
