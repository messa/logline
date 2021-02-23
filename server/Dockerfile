FROM python:3.9-slim

COPY logline_server /src/logline_server
COPY pyproject.toml setup.cfg setup.py /src/

RUN pip install /src

ENTRYPOINT ["logline-server"]
