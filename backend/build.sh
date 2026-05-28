#!/usr/bin/env bash
# exit on error
set -o errexit

cd "$(dirname "$0")"

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py seed_demo --no-input
