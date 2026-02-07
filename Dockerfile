# Use official Python runtime as base image
FROM python:3.10.13

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create a directory for the database (if using Docker volume)
RUN mkdir -p /app/data

# Collect static files (if any)
# RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run Gunicorn (or Django development server for development)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
