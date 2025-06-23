# spectra-analyzer/Dockerfile
FROM python:3.11-slim
WORKDIR /app

# Copy only requirements to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy analyzer application code
COPY app.py .

# Run the analyzer
CMD ["python", "app.py"]
