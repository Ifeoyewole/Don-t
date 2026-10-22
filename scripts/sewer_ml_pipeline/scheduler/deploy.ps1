$ErrorActionPreference = "Stop"
$project = "joint-inspection-510310"
$region = "europe-west2"
$service = "jointinspect-gpu-controller"
$serviceAccount = "jointinspect-gpu-controller@$project.iam.gserviceaccount.com"
$stateBucket = "gs://joint-inspection-510310-orchestration"

gcloud services enable run.googleapis.com cloudscheduler.googleapis.com batch.googleapis.com compute.googleapis.com storage.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project=$project
gcloud iam service-accounts describe $serviceAccount --project=$project 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud iam service-accounts create jointinspect-gpu-controller --project=$project --display-name="JointInspect GPU controller"
}

gcloud storage buckets describe $stateBucket 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud storage buckets create $stateBucket --project=$project --location=$region --uniform-bucket-level-access
}

gcloud projects add-iam-policy-binding $project --member="serviceAccount:$serviceAccount" --role="roles/batch.jobsViewer" --quiet
gcloud projects add-iam-policy-binding $project --member="serviceAccount:$serviceAccount" --role="roles/compute.viewer" --quiet
gcloud storage buckets add-iam-policy-binding $stateBucket --member="serviceAccount:$serviceAccount" --role="roles/storage.objectAdmin"

gcloud run deploy $service --project=$project --region=$region --source=. --service-account=$serviceAccount --no-allow-unauthenticated --ingress=all --min=0 --max=1 --cpu=1 --memory=512Mi --concurrency=1 --timeout=60 --set-env-vars="STATE_BUCKET=joint-inspection-510310-orchestration,SUBMISSION_ENABLED=false,CAMPAIGN_CAP_USD=100,CREDIT_RESERVE_USD=50"

# Public network reachability is required for Vercel, but IAM authentication remains mandatory.
gcloud run services add-iam-policy-binding $service --project=$project --region=$region --member="serviceAccount:joint-inspect-vercel-invoker@$project.iam.gserviceaccount.com" --role="roles/run.invoker" --quiet

Write-Host "Controller deployed in dry-run mode. Do not create the Scheduler trigger until quota and financial preflights are verified."
