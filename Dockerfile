FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 app:app
# Cache bust Tue Apr 21 16:22:27 UTC 2026
# redeploy Thu Apr 23 15:22:09 UTC 2026
