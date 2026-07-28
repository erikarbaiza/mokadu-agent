FROM python:3.11-slim

# Node.js 20
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py server.py ./

# Node.js Baileys
COPY baileys/ ./baileys/
RUN cd baileys && npm ci --only=production

COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
