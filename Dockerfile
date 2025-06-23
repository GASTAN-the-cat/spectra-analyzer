# spectra-analyzer/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install only psycopg2
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy analyzer code
COPY app.py .

# Run the analyzer
CMD ["python", "app.py"]
