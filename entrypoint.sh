#!/bin/bash

echo "Starting Gunicorn..."
exec python3 -m gunicorn api:app --bind 0.0.0.0:10000
