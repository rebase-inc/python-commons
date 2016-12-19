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

RUN pyvenv /venv && \
    source /venv/bin/activate && \
    pip --quiet install --upgrade pip && \
    pip --quiet install \
      wheel \
      pypiserver \
      passlib \
      twisted \
      python-magic && \
    mkdir -p /usr/src/app && \
    mkdir -p /usr/src/app/build

WORKDIR /usr/src/app

COPY ./libs ./libs
COPY ./build_packages.sh ./build_packages.sh
RUN source /venv/bin/activate && ./build_packages.sh && rm -rf /usr/src/app/libs

CMD ["/venv/bin/pypi-server", "--server", "twisted", "--overwrite", "-p", "8080", "-P", ".", "-a", ".", "/usr/src/app/build"]
