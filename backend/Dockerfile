FROM python:3.11-slim

# Install base system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv as requested
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency manifests
COPY requirements.txt .

# Install packages using uv rapidly and securely
RUN uv pip install --system -r requirements.txt

# Copy backend source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
