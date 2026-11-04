FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime
WORKDIR /workspace
RUN python -m pip install --no-cache-dir torchvision==0.20.1 google-cloud-storage==3.4.1 'pillow>=10,<14'
COPY training/inspect_view_representation.py /workspace/training/inspect_view_representation.py
COPY training/evaluate_inspect_view_candidate.py /workspace/training/evaluate_inspect_view_candidate.py
COPY training/data_sources/canonical_labels.json /workspace/training/data_sources/canonical_labels.json
COPY scripts/external_datasets/smoke_masked_trainer.py /workspace/smoke_masked_trainer.py
RUN python /workspace/smoke_masked_trainer.py
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "training/inspect_view_representation.py"]
