FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential libpq-dev curl \
  && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"


COPY pyproject.toml uv.lock* requirements*.txt* /app/

RUN python -m venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

RUN /app/.venv/bin/python -m pip install --upgrade pip setuptools wheel
RUN if [ -f requirements.full.txt ]; then \
  /app/.venv/bin/python -m pip install -r requirements.full.txt; \
  else \
  /app/.venv/bin/python -m pip install -r requirements.txt; \
  fi

RUN /app/.venv/bin/python -m pip install --no-cache-dir \
  daphne celery redis django-cors-headers channels psycopg[binary,pool]>=3.1

COPY . /app

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"
