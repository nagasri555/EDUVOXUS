#!/usr/bin/env bash
# Build script for Render deployment
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Create upload directories
mkdir -p uploads/notes
mkdir -p uploads/certificates
