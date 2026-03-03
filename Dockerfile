FROM python:3.12-slim

WORKDIR /app

# Install production dependencies first (layer caching)
COPY requirements.txt requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application code (secrets excluded via .dockerignore)
COPY . .

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080

# Allow OAUTHLIB to work over HTTP behind Cloud Run's HTTPS proxy
ENV OAUTHLIB_INSECURE_TRANSPORT=0
ENV OAUTHLIB_RELAX_TOKEN_SCOPE=1

# Gunicorn with gevent for SSE streaming support
CMD exec gunicorn wsgi:app -c gunicorn.conf.py
