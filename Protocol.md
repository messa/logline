Logline Agent - Server Protocol
===============================

Agent connects to the Server using TCP connection.
Default port number 5645 – this number was randomly chosen, not assigned by anybody.

The connection can be wrapped into TLS – in that case both Agent and Server must be configured to use TLS.

Purpose of the connection is to transfer a log file content from Agent to Server.

Example of the connection:

```
Agent (A) connects to Server (S)
A: logline-agent-v1 135\n
A: {"hostname": "server.example.com", "path": "/var/log/something.log", "prefix": {"length": 42, "sha256": "LPJNul+wow4m6DsqxbninhsWHlwfp0JecwQzYpOLmCQ="}}\n
S: ok 16\n
S: {"length": 195}\n
A: data 37 44\n
A: {"offset": 195, "compression": null}\n
A: now the Agent sends the raw log file content
S: ok\n
```

The `prefix` object identifies the log file by hashing its first `length` bytes.
Current Agents send a SHA-256 hash in the `sha256` field. For backward
compatibility, the Server also accepts the legacy `sha1` field (Base64-encoded
SHA-1 digest) sent by older Agents.

Client authentication uses a `client_token` whose hash must match one of the
Server's configured `client_token_hashes`. The Server matches the token against
its modern SHA-256 (hex) hash and, for backward compatibility, also against the
legacy SHA-1 (hex) hash.
