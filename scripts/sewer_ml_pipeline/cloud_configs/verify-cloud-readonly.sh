#!/usr/bin/env bash
set -euo pipefail
PROJECT=joint-inspection-510310
REGION=europe-west2
BUCKET=gs://joint-inspection-510310-data

gcloud config get-value project
gcloud builds list --project "$PROJECT" --region "$REGION" --limit=25 \
    --format='table(id,status,createTime,finishTime)'
gcloud builds list --project "$PROJECT" --region global --limit=25 \
    --format='table(id,status,createTime,finishTime)'
gcloud run services describe pipe-joint-api --project "$PROJECT" \
    --region "$REGION" --format='value(status.latestReadyRevisionName)'
gcloud storage ls "$BUCKET/datasets/sewer-ml/" || true
gcloud storage ls "$BUCKET/models/candidates/" || true

