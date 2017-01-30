FROM python:alpine

RUN apk --quiet update && \
    apk --quiet add \
        bash \
        ca-certificates \
        gcc \
        musl-dev \
        py-virtualenv \
        python3-dev \
        docker

RUN python3.6 -m venv /venv && \
    source /venv/bin/activate && \
    pip --quiet install --upgrade pip && \
    pip --quiet install \
      wheel \
      pypiserver \
      passlib \
      twisted \
      python-magic && \
    mkdir -p /usr/src/app && \
    mkdir -p /usr/src/app/wheels

WORKDIR /usr/src/app

COPY libs libs
RUN source /venv/bin/activate && \
    mkdir -p  /tmp/egg_info /tmp/build && \
    python libs/setup.py \
        build -b /tmp/build/ \
        egg_info -e /tmp/egg_info \
        bdist_wheel \
            --universal \
            --dist-dir /usr/src/app/wheels && \
     rm -rf /usr/src/app/libs

CMD ["/venv/bin/pypi-server", "--server", "twisted", "--overwrite", "-p", "8080", "-P", ".", "-a", ".", "/usr/src/app/wheels"]
