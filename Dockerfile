FROM python:3.12-slim

WORKDIR /app

# Install Node.js
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install opendevbrowser
RUN npm install -g opendevbrowser

COPY . .

# Default command for the web app
CMD ["uvicorn", "eagle_gallery_app:app", "--host", "0.0.0.0", "--port", "34920"]
