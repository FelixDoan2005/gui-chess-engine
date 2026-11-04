FROM python:3.11-slim

# PyPy, so Felis thinks about 3x faster (the server itself runs on normal Python)
RUN apt-get update && apt-get install -y --no-install-recommends curl bzip2 \
    && curl -sL https://downloads.python.org/pypy/pypy3.11-v7.3.20-linux64.tar.bz2 | tar -xj -C /opt \
    && apt-get purge -y curl bzip2 && rm -rf /var/lib/apt/lists/*
ENV PYPY_PATH=/opt/pypy3.11-v7.3.20-linux64/bin/pypy3

WORKDIR /code


COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

COPY engine/ engine/
COPY ui/ ui/
COPY assets/images/pieces/ assets/images/pieces/
COPY web/ web/

CMD ["fastapi", "run", "web/server.py", "--port", "8080"]
