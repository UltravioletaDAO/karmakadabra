# Karmacadabra Marketplace - Central Agent Discovery Service
# Build context: project root (karmacadabra/)
# Build: docker build -f agents/marketplace/Dockerfile -t marketplace .

FROM python:3.11-slim

WORKDIR /app/agents/marketplace

# Install dependencies
COPY agents/marketplace/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agents/marketplace/main.py .

# Copy agent cards and profiles from demo directory
# The code expects: BASE_DIR / "demo/profiles" where BASE_DIR is 3 levels up
COPY demo/cards /app/demo/cards
COPY demo/profiles /app/demo/profiles

# Expose port
EXPOSE 9000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:9000/health', timeout=5)" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
