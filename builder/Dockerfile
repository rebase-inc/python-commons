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
    pip install wheel

VOLUME /python-commons
WORKDIR /python-commons

CMD ["./builder/build"]
