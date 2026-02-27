FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt api/requirements.txt
COPY worker/requirements.txt worker/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt -r worker/requirements.txt

COPY api/ api/
COPY worker/ worker/
COPY spotify-2023.csv /app/spotify-2023.csv
