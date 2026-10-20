FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 4 --timeout 60 controller:app
