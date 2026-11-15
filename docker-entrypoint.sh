#!/bin/sh
set -eu

# /app/config.json is a symlink to /app/data/config.json baked into the image.
config_path=/app/data/config.json
default_path=/app/defaults/config.json

mkdir -p /app/data

if [ -d "$config_path" ]; then
  echo "Configuration path is a directory, expected a file: $config_path" >&2
  exit 1
fi

if [ ! -f "$config_path" ]; then
  # Copy only on first run, never replace user edits on image updates.
  cp "$default_path" "$config_path"
  echo "Initialized persistent config.json"
fi

exec "$@"
