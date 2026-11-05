FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend /app/backend
COPY preview-model.pt /app/preview-model.pt
ENV JOINTINSPECT_PREVIEW_MODEL_PATH=/app/preview-model.pt JOINTINSPECT_PREVIEW_ENABLED=true OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CMD ["sh","-c","exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
