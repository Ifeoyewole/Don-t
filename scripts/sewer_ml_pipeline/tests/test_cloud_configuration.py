from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_vertex_contract_uses_gcs_and_pinned_gpu():
    config = (ROOT / "cloud_configs/vertex-v3.example.yaml").read_text()
    for value in ("machineType: n1-standard-8", "acceleratorType: NVIDIA_TESLA_T4",
                  "acceleratorCount: 1", "REPLACE_WITH_VERIFIED_DIGEST"):
        assert value in config
    assert config.count("=gs://") == 5
    assert "--output-prefix=gs://" in config


def test_container_versions_and_cloud_entrypoint_are_pinned():
    dockerfile = (ROOT / "cloud_configs/v3-worker.Dockerfile").read_text()
    for value in ("pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime", "torchvision==0.20.1",
                  "onnx==1.17.0", "onnxruntime==1.20.1", "numpy==1.26.4"):
        assert value in dockerfile
    assert 'ENTRYPOINT ["python", "scripts/sewer_ml_pipeline/cloud_train_v3.py"]' in dockerfile
