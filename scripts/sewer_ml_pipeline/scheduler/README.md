# JointInspect GPU campaign controller

This is a separate, CPU-only Cloud Run controller. It is fail-closed and defaults
to `SUBMISSION_ENABLED=false`. It must never be deployed into the production API
service.

The operator dashboard uses Vercel Workload Identity Federation to call this
service. Cloud Run therefore permits external ingress but remains IAM-protected;
only the scheduler service account and the dedicated Vercel invoker service
account receive `roles/run.invoker`.

The current project cannot submit a GPU VM because the global Compute Engine
`GPUS_ALL_REGIONS` quota is zero. Regional `NVIDIA_L4_GPUS=1` quotas do not
override that global limit. Promotional-credit balances are not treated as
discoverable or enforceable through budget alerts; a fresh operator-verified
balance is required before submission can ever be enabled.

Persistent state and the atomic lease are stored in the dedicated bucket under
`gs://joint-inspection-510310-orchestration/orchestration/gpu-scheduler/v1/`
using GCS generation preconditions. The controller has no write permission to
the dataset/model bucket. It publishes `status.json` for an
operator-readable status surface.

Deployment remains dry-run until all of the following are true:

1. `GPUS_ALL_REGIONS >= 1`.
2. A fresh promotional-credit balance and expiry are operator verified.
3. Worst-case liability stays under the configured campaign cap and preserves
   the $50 reserve.
4. A user explicitly approves setting `SUBMISSION_ENABLED=true`.

Cloud budget alerts are advisory and cannot guarantee zero personal charges.
