#!/bin/bash
cd "$(dirname "$0")"

if [ -f "./dist/client" ]; then
  ./dist/client
else
  source venv/bin/activate
  python client.py
fi