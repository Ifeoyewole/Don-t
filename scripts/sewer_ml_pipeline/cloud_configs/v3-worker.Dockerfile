# Build only in Google Cloud Build / Artifact Registry, never on developer PC.
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime
WORKDIR /workspace
RUN python -m pip install --no-cache-dir torchvision==0.20.1 \
    onnx==1.17.0 onnxruntime==1.20.1 onnxscript==0.1.0 \
    google-cloud-storage requests 'pillow>=10,<14' numpy==1.26.4
COPY scripts/sewer_ml_pipeline/ /workspace/scripts/sewer_ml_pipeline/
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "scripts/sewer_ml_pipeline/train_v3.py"]

