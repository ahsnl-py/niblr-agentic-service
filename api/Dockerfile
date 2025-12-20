# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory to /app (parent of api package)
WORKDIR /app

# Copy API package files
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/uv.lock /app/api/uv.lock
COPY api/README.md /app/api/README.md
COPY api/__init__.py /app/api/__init__.py
COPY api/__main__.py /app/api/__main__.py
COPY api/src /app/api/src

# Install dependencies using uv (respect pyproject/uv.lock)
# Run from api directory so uv can find pyproject.toml and create venv there
WORKDIR /app/api
RUN uv sync --frozen --no-dev

# Set working directory back to /app so Python can import 'api' as a package
WORKDIR /app

# Expose port (Cloud Run uses PORT env var, but 8080 is standard)
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV API_PORT=8080

# Run the API using the venv's Python directly
# This ensures:
# 1. We use the venv created by uv sync in /app/api/.venv
# 2. Python can import 'api' as a package from /app/api/
# 3. All dependencies are available from the venv
ENTRYPOINT ["/app/api/.venv/bin/python", "-m", "api"]

