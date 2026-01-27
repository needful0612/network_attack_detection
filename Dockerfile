FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    curl \
    gzip \
    libpcap-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x get_data.sh
ENV PYTHONPATH=/app

EXPOSE 8000
# Default command: i override this in docker-compose for now
CMD ["python", "scripts/svm/serve.py"]