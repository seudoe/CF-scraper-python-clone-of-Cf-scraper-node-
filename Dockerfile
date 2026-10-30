FROM python:3.11-slim 

# Copy uv directly from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv 

WORKDIR /app

# Copy dependency files first for layer caching 
COPY pyproject.toml uv.lock ./

# Install only the core dependencies (skips the scraper extra)
RUN uv sync --frozen --no-dev 

# Copy the rest of the application
COPY lib/ ./lib/
COPY templates/ ./templates/
COPY app_hf.py .
COPY .env.example .env

EXPOSE 7860 
ENV PORT=7860 
ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "120", "app_hf:app"]