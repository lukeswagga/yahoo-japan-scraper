FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

# Copy Discord bot files
COPY secure_discordbot.py .
COPY database_manager.py .

# Run Discord bot in background, then scraper
CMD ["sh", "-c", "python secure_discordbot.py & sleep 15 && python yahoo_sniper.py"]

