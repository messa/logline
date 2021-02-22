Logline Agent - Server Protocol
===============================

Agent connects to the Server using TCP connection.
Default port number 5645 – this number was randomly chosen, not assigned by anybody.

The connection can be wrapped into TLS – in that case both Agent and Server must be configured to use TLS.

Purpose of the connection is to transfer a log file content from Agent to Server.

Example of the connection:

```
Agent (A) connects to Server (S)
A: logline-agent-v1\n
A: {"hostname": "server.example.com", "path": "/var/log/something.log", "prefix": {"length": 42, "sha1": "aTQsXDnlrl8Ad67MMsD4GBH7gZM="}}\n
S: ok\n
S: {"length": 195}\n
A: data\n
A: now the Agent sends the raw log file content
A: just as it appears in the original file
A: no reply or response from Server is expected
```
