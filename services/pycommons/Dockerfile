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

RUN pyvenv /venv && \
    source /venv/bin/activate && \
    pip install --upgrade pip && \
    pip install wheel && \
    pip install pypiserver && \
    pip install passlib && \
    pip install twisted && \
    mkdir -p /wheelhouse && \
    mkdir -p /workdir

WORKDIR /workdir

COPY ./libs /workdir/libs
COPY ./build_packages.sh /workdir/build_packages.sh
RUN source /venv/bin/activate && ./build_packages.sh

CMD ["/venv/bin/pypi-server", "--server", "twisted", "--overwrite", "-p", "8080", "-P", ".", "-a", ".", "/wheelhouse"]
