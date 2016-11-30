FROM python:alpine

RUN apk update && \
    apk add \
        bash \
        ca-certificates \
        py-virtualenv \
        python3-dev \
        docker

RUN pyvenv /venv/build && \
    source /venv/build/bin/activate && \
    pip install --upgrade pip && \
    pip install wheel && \
    pip install pypiserver && \
    pip install passlib && \
    mkdir -p /wheelhouse

CMD ["/venv/build/bin/pypi-server", "-p", "8080", "-P", ".", "-a", ".", "/wheelhouse"]
