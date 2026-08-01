FROM python:3.9-slim

WORKDIR /app

# Copy requirements
COPY requirements-hf.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements-hf.txt

# Copy application code
COPY lib/ ./lib/
COPY templates/ ./templates/
COPY app_hf.py .
COPY .env.example .env

# Expose port (HF Spaces uses 7860)
EXPOSE 7860

# Set environment variables
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "120", "app_hf:app"]
