# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy server source code
COPY argus ./argus

ENV PYTHONUNBUFFERED=1

# Default command to run the MCP server over stdio; override with
# `--transport sse --host 0.0.0.0 --port 8000` (or ARGUS_TRANSPORT=sse etc.)
# to serve over SSE instead.
CMD ["python", "-u", "-m", "argus", "--transport", "stdio"]
