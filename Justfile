# Justfile (repo root)

set dotenv-load := true
set quiet := false
set shell := ["bash", "-uc"]

DJANGO_DIR := "apis"              # folder that contains manage.py
PY := ".venv/bin/python"          # venv python

venv:
  if [ ! -x {{PY}} ]; then python3 -m venv .venv; fi

install: venv
  {{PY}} -m pip install -U pip wheel setuptools
  {{PY}} -m pip install -r requirements.txt

assets:
  {{PY}} {{DJANGO_DIR}}/manage.py clean_assets
  {{PY}} {{DJANGO_DIR}}/manage.py populate_assets

run:
  {{PY}} {{DJANGO_DIR}}/manage.py runserver 0.0.0.0:8000

manage *args:
  {{PY}} {{DJANGO_DIR}}/manage.py {{args}}
