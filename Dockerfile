FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App files
COPY app.py .
COPY templates/ templates/
COPY static/ static/

# Create audio output directory
RUN mkdir -p static/audio

EXPOSE 5001

CMD ["python", "app.py"]
