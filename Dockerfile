FROM python:3.10.0 as python-base

ARG APP_NAME=apps
ARG APP_PATH=/opt/$APP_NAME
ARG PYTHON_VERSION=3.10.0
ARG POETRY_VERSION=1.3.1

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 
ENV \
    POETRY_VERSION=$POETRY_VERSION \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# System deps:
RUN apt-get update \
  && apt-get install --no-install-recommends -y \
    bash \
    build-essential \
    curl \
    gettext \
    git \
    libpq-dev \
    wget \
  # Cleaning cache:
  && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="$POETRY_HOME/bin:$PATH"

# Copy and install dependencies
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

# Export to requirements.txt
RUN poetry export -f requirements.txt --output requirements.txt

# Stage: Build
FROM python:3.10.0 as build
ARG APP_NAME=apps
ARG APP_PATH=/opt/$APP_NAME
ARG user=appuser
ARG group=appuser
ARG uid=1000
ARG gid=1000

ENV \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

ENV \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 

# ENV \
#     PRIMARY_DB_NAME=${PRIMARY_DB_NAME} \
#     PRIMARY_DB_HOST=${PRIMARY_DB_HOST} \
#     PRIMARY_DB_USERNAME=${PRIMARY_DB_USERNAME} \
#     PRIMARY_DB_PASSWORD=${PRIMARY_DB_PASSWORD} \
#     PRIMARY_DB_PORT=${PRIMARY_DB_PORT} \
#     SECRET_KEY=${SECRET_KEY} \
#     ALLOWED_CLIENT_HOSTS=${ALLOWED_CLIENT_HOSTS} \
#     DEBUG=True \
#     EVENT_DB_HOST=${EVENT_DB_HOST} \
#     EVENT_DB_NAME=${EVENT_DB_NAME} \
#     EVENT_DB_USERNAME=${EVENT_DB_USERNAME} \
#     EVENT_DB_PASSWORD=${EVENT_DB_PASSWORD} \
#     EVENT_DB_PORT=${EVENT_DB_PORT} \
#     EVENT_DB_ATTR_SSL_CA=/etc/ssl/cert.pem \
#     REDIS_HOSTNAME=${REDIS_HOSTNAME} \
#     DATABASE=${DATABASE}

COPY --from=python-base requirements.txt ./
RUN pip install -r requirements.txt

# Set up non root user
RUN groupadd -g ${gid} ${group} && useradd -u ${uid} -g ${group} -s /bin/sh ${user}

# Set up working directory and add ownership to non root user
RUN mkdir $APP_PATH
RUN chown -R ${user}:${group} $APP_PATH

# Copy source code
WORKDIR $APP_PATH
COPY . .
COPY entrypoint.sh docker-entrypoint.sh
RUN chmod +x docker-entrypoint.sh

# Check for files
RUN ls

# Change user
USER ${user}

# Run entrypoint
ENTRYPOINT ["/opt/apps/docker-entrypoint.sh"]
