FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node deps for Spider_XHS JS signing
COPY spider_xhs/package.json spider_xhs/
RUN cd spider_xhs && npm install --omit=dev

# Source code
COPY . .

# Build frontend for production
WORKDIR /app/frontend
RUN npm install && npm run build

WORKDIR /app

EXPOSE 8000

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
