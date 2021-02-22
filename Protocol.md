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
A: {"hostname": "server.example.com", "path": "/var/log/something.log", "prefix": {"length": 42, "sha1": "aTQsXDnlrl8Ad67MMsD4GBH7gZM="}}\n
S: ok 16\n
S: {"length": 195}\n
A: data 37 44\n
A: {"offset": 195, "compression": null}\n
A: now the Agent sends the raw log file content
S: ok\n
```
