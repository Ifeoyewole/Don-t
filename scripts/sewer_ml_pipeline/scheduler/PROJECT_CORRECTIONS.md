# Project-specific corrections

The supplied scheduler brief is directionally correct, with these JointInspect
corrections applied:

1. Regional L4 quota is not sufficient. The project currently has
   `GPUS_ALL_REGIONS=0`, which blocks every Compute Engine GPU allocation. The
   controller therefore blocks before regional failover.
2. The stricter existing $100 campaign budget takes precedence over the
   proposed $240 envelope. The $50 promotional-credit reserve is additional.
3. Promotional-credit balance and expiry are not assumed to be reliably
   available from project billing APIs. They must be freshly operator verified.
4. Cloud budget alerts are advisory, not a zero-personal-spend guarantee. New
   submissions fail closed when cost, credit, or pricing inputs are unavailable.
5. Cloud Scheduler did not previously exist in this project. A dedicated job is
   created paused; it is not attached to the production API service.
6. Controller state uses a dedicated bucket. The controller has no write access
   to the Sewer-ML dataset or model artifact bucket.
7. The currently deployed controller is deliberately observation-only. Its
   service account has Batch Viewer rather than Batch Editor, and
   `SUBMISSION_ENABLED=false`. Enabling real mutation requires a reviewed code
   addition, narrower IAM, a positive global GPU quota, fresh financial inputs,
   and explicit approval.
8. Regional support does not prove live capacity. Only Batch allocation events
   are accepted as capacity evidence.
