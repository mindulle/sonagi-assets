FROM python:3.12-slim

WORKDIR /app

# Install Node.js and apply OS security updates
RUN apt-get update && apt-get upgrade -y && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install opendevbrowser
RUN npm install -g opendevbrowser

COPY . .

# 릴리즈 워크플로가 build-arg로 주입한다(.git이 이미지에 없어 git describe 불가).
ARG PRESS_VERSION=dev
ENV PRESS_VERSION=${PRESS_VERSION}

# Default command for the web app
CMD ["uvicorn", "asset_hub_app:app", "--host", "0.0.0.0", "--port", "34920"]
