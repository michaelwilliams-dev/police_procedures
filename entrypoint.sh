#!/bin/bash
# Render always starts this from the root folder

echo "Starting Gunicorn..."
exec gunicorn api:app --bind 0.0.0.0:10000
