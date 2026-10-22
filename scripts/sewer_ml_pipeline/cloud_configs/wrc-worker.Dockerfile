FROM tensorflow/tensorflow:2.15.1-gpu
WORKDIR /workspace
RUN python -m pip install --no-cache-dir google-cloud-storage 'pillow>=10,<14'
COPY scripts/sewer_ml_pipeline/ /workspace/scripts/sewer_ml_pipeline/
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/workspace/scripts/sewer_ml_pipeline
ENTRYPOINT ["python", "scripts/sewer_ml_pipeline/cloud_wrc_train.py"]
