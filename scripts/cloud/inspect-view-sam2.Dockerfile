# Built remotely in Cloud Build. No weights are bundled in this image.
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1 SAM2_BUILD_CUDA=0 PYTHONPATH=/workspace
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir torchvision==0.20.1 \
    'numpy>=1.26,<2' 'opencv-python-headless>=4.9,<5' \
    'pillow>=10.3,<11' 'google-cloud-storage==3.4.1' 'google-cloud-secret-manager>=2.20,<3' \
    'hydra-core>=1.3.2,<1.4' 'iopath>=0.1.10,<0.2' \
    'tqdm>=4.66,<5' 'fastapi>=0.111,<0.112' 'scipy>=1.13,<2' \
    'pydantic>=2.7,<3' 'pydantic-settings>=2.2,<3' 'python-multipart>=0.0.9'
RUN git clone https://github.com/facebookresearch/sam2.git /opt/sam2 \
  && cd /opt/sam2 && git checkout 2b90b9f5ceec907a1c18123530e92e794ad901a4 \
  && python -m pip install --no-cache-dir --no-deps -e /opt/sam2
COPY backend/ /workspace/backend/
COPY scripts/benchmark_inspect_view_sam2_fusion.py /workspace/scripts/benchmark_inspect_view_sam2_fusion.py
COPY scripts/cloud/inspect_view_sam2_vertex.py /workspace/scripts/cloud/inspect_view_sam2_vertex.py
COPY scripts/cloud/inspect_view_sam2_batch_vertex.py /workspace/scripts/cloud/inspect_view_sam2_batch_vertex.py
ENTRYPOINT ["python", "-m", "scripts.cloud.inspect_view_sam2_vertex"]
