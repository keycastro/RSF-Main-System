FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-production.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt
COPY . .
RUN mkdir -p /data/message_uploads /data/profile_pictures /data/client_attachments /data/backups
ENV DATABASE_PATH=/data/rsf_sales_partner.db \
    MESSAGE_UPLOAD_DIR=/data/message_uploads \
    PROFILE_PICTURE_DIR=/data/profile_pictures \
    CLIENT_ATTACHMENT_DIR=/data/client_attachments \
    BACKUP_DIR=/data/backups \
    HOST=0.0.0.0 \
    PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "gunicorn --workers 1 --threads 8 --timeout 60 --bind 0.0.0.0:${PORT:-8080} wsgi:application"]
