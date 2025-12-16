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
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy API package files
COPY api/ /app/api/
COPY api/pyproject.toml /app/pyproject.toml
COPY api/uv.lock /app/uv.lock
COPY api/README.md /app/README.md

# Install dependencies using uv
WORKDIR /app
RUN uv sync --frozen --no-dev

# Expose port
EXPOSE 8083

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV API_PORT=8083

# Run the API
ENTRYPOINT ["uv", "run", "api"]

