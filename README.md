Logline
=======

Live synchronization of log files from multiple computers (usually VMs, servers…) to a single place.

(Log file = a regular file that only grows (new content is only appended) and can be rotated.)

Consists of two pieces:

- **agent** reads the logs and sends their content to the server via (encrypted) TCP connection
- **server** listens on a TCP port, receives data from agents and manages a mirror of the log files processed by agents

The TCP connection can be encrypted via SSL/TLS – using a certificate for example from LetsEncrypt.org or a self-signed one.


Development
-----------

The project uses [uv](https://docs.astral.sh/uv/) for dependency management and packaging.
The `agent` and `server` packages are organized as a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).

Install the dependencies (creates a virtual environment in `.venv`):

```shell
uv sync
```

Run the tests:

```shell
uv run pytest agent/tests
uv run pytest server/tests
uv run pytest e2e_tests
```

or simply:

```shell
make run_e2e_tests
```

Build the distribution artifacts:

```shell
uv build --package logline-agent
uv build --package logline-server
```
