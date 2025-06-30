# Standard Dockerfile without BuildKit extensions
FROM python:3.10-slim

# (Optional) Use default Debian mirrors for better reliability
RUN find /etc/apt/ -name '*.list' -exec sed -i 's|http://deb.debian.org|http://ftp.de.debian.org|g' {} +

ENV PYTHONPATH=/app

# Set env vars
ENV PYTHONUNBUFFERED=1 \
    REDIS_IP=10.58.64.83 \
    REDIS_PORT=6379 \
    REDIS_DB=0 \
    TZ=Europe/Athens \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install minimal dependencies (no git)
RUN apt-get clean && rm -rf /var/lib/apt/lists/* && \
    for i in 1 2 3; do \
      apt-get update --allow-releaseinfo-change -o Acquire::http::No-Cache=True && \
      apt-get install -y --no-install-recommends \
        curl libgl1 libglib2.0-0 python3-opencv \
        libffi-dev libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0 \
        libxml2 libxslt1.1 libjpeg-dev zlib1g-dev fonts-dejavu-core \
        --fix-missing && \
      dpkg --configure -a && \
      apt-get clean && rm -rf /var/lib/apt/lists/* && break || sleep 5; \
    done


# Create logs directory as root
RUN mkdir -p /app/logs

# Copy project files as root
COPY requirements.txt start_worker.sh celery_config.py tasks.py list_of_instruments.txt orasis_investment_principles.txt /app/

# Create module structure
RUN mkdir -p /app/portfolio_generator

# Copy all necessary Python files
COPY portfolio_generator/ /app/portfolio_generator/

# Ensure script is executable
RUN chmod +x /app/start_worker.sh

# Install Python dependencies (with GitPython)
RUN pip install --timeout 180 --no-cache-dir -r /app/requirements.txt gitpython

# Create non-root user *after all file copies*
RUN useradd -ms /bin/bash celeryuser

# Fix permissions for celeryuser
RUN chown -R celeryuser:celeryuser /app

# Switch to non-root user
USER celeryuser

# Run the worker
CMD ["bash", "start_worker.sh"]
