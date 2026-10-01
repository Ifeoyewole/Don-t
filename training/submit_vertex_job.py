"""Vertex AI Custom Job Management Utility.

Submit, inspect, stream logs, and cancel custom training jobs on Google Cloud Vertex AI
for Pipe Joint AI/CV models.
"""

import argparse
import subprocess
import sys

PROJECT_ID = "joint-inspection-510310"
REGION = "europe-west2"
TRAINER_SA = f"joint-inspection-trainer@{PROJECT_ID}.iam.gserviceaccount.com"
DEFAULT_IMAGE = f"europe-west2-docker.pkg.dev/{PROJECT_ID}/joint-inspection-training/pipe-joint-trainer:v1"
STAGING_BUCKET = f"gs://{PROJECT_ID}-data"


def submit_job(display_name: str, image_uri: str, epochs: int, model_type: str):
    """Submits a custom training job to Vertex AI using gcloud."""
    cmd = [
        "gcloud", "ai", "custom-jobs", "create",
        f"--region={REGION}",
        f"--project={PROJECT_ID}",
        f"--display-name={display_name}",
        f"--worker-pool-spec=machine-type=e2-standard-4,container-image-uri={image_uri}",
        f"--service-account={TRAINER_SA}",
        f"--args=--epochs={epochs},--model_type={model_type},--data_bucket={PROJECT_ID}-data",
    ]
    print(f"Executing: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, shell=sys.platform == "win32")


def list_jobs():
    """Lists existing Vertex AI custom training jobs."""
    cmd = [
        "gcloud", "ai", "custom-jobs", "list",
        f"--region={REGION}",
        f"--project={PROJECT_ID}",
        "--format=table(name,displayName,state,createTime,endTime)",
    ]
    subprocess.run(cmd, check=True, shell=sys.platform == "win32")


def stream_logs(job_id: str):
    """Streams live logs from a running Vertex AI custom training job."""
    cmd = [
        "gcloud", "ai", "custom-jobs", "stream-logs",
        job_id,
        f"--region={REGION}",
        f"--project={PROJECT_ID}",
    ]
    subprocess.run(cmd, check=True, shell=sys.platform == "win32")


def cancel_job(job_id: str):
    """Cancels a running Vertex AI custom training job."""
    cmd = [
        "gcloud", "ai", "custom-jobs", "cancel",
        job_id,
        f"--region={REGION}",
        f"--project={PROJECT_ID}",
    ]
    subprocess.run(cmd, check=True, shell=sys.platform == "win32")


def describe_job(job_id: str):
    """Describes a specific Vertex AI custom training job."""
    cmd = [
        "gcloud", "ai", "custom-jobs", "describe",
        job_id,
        f"--region={REGION}",
        f"--project={PROJECT_ID}",
    ]
    subprocess.run(cmd, check=True, shell=sys.platform == "win32")


def main():
    parser = argparse.ArgumentParser(description="Vertex AI Custom Training Management for Pipe Joint Models")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    submit_p = subparsers.add_parser("submit", help="Submit new custom training job")
    submit_p.add_argument("--display-name", default="pipe-joint-supervised-training-v1")
    submit_p.add_argument("--image", default=DEFAULT_IMAGE)
    submit_p.add_argument("--epochs", type=int, default=10)
    submit_p.add_argument("--model-type", choices=["segmenter", "classifier"], default="segmenter")

    subparsers.add_parser("list", help="List custom training jobs")

    logs_p = subparsers.add_parser("stream-logs", help="Stream job logs")
    logs_p.add_argument("job_id", help="Vertex AI Custom Job ID")

    cancel_p = subparsers.add_parser("cancel", help="Cancel training job")
    cancel_p.add_argument("job_id", help="Vertex AI Custom Job ID")

    describe_p = subparsers.add_parser("describe", help="Inspect job details")
    describe_p.add_argument("job_id", help="Vertex AI Custom Job ID")

    args = parser.parse_args()

    if args.command == "submit":
        submit_job(args.display_name, args.image, args.epochs, args.model_type)
    elif args.command == "list":
        list_jobs()
    elif args.command == "stream-logs":
        stream_logs(args.job_id)
    elif args.command == "cancel":
        cancel_job(args.job_id)
    elif args.command == "describe":
        describe_job(args.job_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
