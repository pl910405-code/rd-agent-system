FROM python:3.11-slim

WORKDIR /app

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libgl1-mesa-glx libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Data dirs
RUN mkdir -p /app/data/uploads /app/data/kb

CMD ["python", "backend/server.py"]
