Logline
=======

Live synchronization of log files from multiple computers (usually VMs, servers…) to a single place.

(Log file = a regular file that only grows (new content is only appended) and can be rotated.)

Consists of two pieces:

- *agent* reads the logs and sends their content to the server via (encrypted) TCP connection
- *server* listens on a TCP port, receives data from agents and manages a mirror of the log files processed by agents

The TCP connection can be encrypted via SSL/TLS – using a certificate for example from LetsEncrypt.org or a self-signed one.
