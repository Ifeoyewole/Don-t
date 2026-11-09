# Isolated research image only. Never replace the production API image.
FROM europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:bf93efdab86558f29a708e2719bdf511953b2c26d87c6cc7b57612ab0b8f0304
RUN python -m pip install --no-cache-dir onnxruntime==1.18.1
COPY backend/ /workspace/backend/
COPY scripts/cloud/ /workspace/scripts/cloud/
ENTRYPOINT ["python", "-m", "scripts.cloud.sewer_unified_worker"]
