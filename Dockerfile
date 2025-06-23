# spectra-analyzer/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Copy & install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy analyzer code
COPY app.py .

# Run the analyzer on container start
CMD ["python", "app.py"]
