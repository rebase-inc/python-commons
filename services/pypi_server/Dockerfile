FROM python:alpine

RUN apk update && \
    apk add \
        bash \
        ca-certificates \
        gcc \
        musl-dev \
        py-virtualenv \
        python3-dev \
        docker

RUN pyvenv /venv/build && \
    source /venv/build/bin/activate && \
    pip install --upgrade pip && \
    pip install wheel && \
    pip install pypiserver && \
    pip install passlib && \
    pip install twisted && \
    mkdir -p /wheelhouse

COPY ./run.sh run.sh

CMD ["/venv/build/bin/pypi-server", "--server", "twisted", "--overwrite", "-p", "8080", "-P", ".", "-a", ".", "/wheelhouse"]
