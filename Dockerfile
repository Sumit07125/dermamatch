FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the AI model to speed up startup times on HF Spaces
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the entire project
COPY . .

# Hugging Face exposes exactly port 7860
EXPOSE 7860

# Make the start script executable
RUN chmod +x start.sh

# Run the startup script which launches both backend and frontend
CMD ["./start.sh"]
