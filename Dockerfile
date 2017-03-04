FROM python:alpine

RUN apk --quiet update && \
    apk --quiet add \
        bash \
        ca-certificates \
        gcc \
        musl-dev \
        py-virtualenv \
        python3-dev

RUN python3.6 -m venv /venv && \
    source /venv/bin/activate && \
    pip --quiet install --upgrade pip && \
    pip --quiet install \
      wheel \
      pypiserver \
      passlib \
      twisted \
      python-magic && \
    mkdir -p /usr/src/app/wheels /tmp/egg_info /tmp/build

WORKDIR /usr/src/app

COPY libs libs

COPY build_packages.sh build_packages.sh

RUN source /venv/bin/activate && ./build_packages.sh

CMD ["/venv/bin/pypi-server", "--server", "twisted", "--overwrite", "-p", "8080", "-P", ".", "-a", ".", "/usr/src/app/wheels"]
