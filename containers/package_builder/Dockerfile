FROM python:alpine

RUN apk update && \
    apk add \
        bash \ 
        ca-certificates \
        curl \
        py-virtualenv \
        python3-dev \
        docker

RUN pyvenv /venv/build && \
    source /venv/build/bin/activate && \
    pip install --upgrade pip && \
    pip install wheel && \
    pip install twine

VOLUME /python-commons
WORKDIR /python-commons

CMD ["./containers/package_builder/build.sh"]
