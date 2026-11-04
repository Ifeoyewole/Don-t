# Engineering preview acquisition round and training handoff

## Acquired and inspected

- TUBERS, Zenodo 20136698: CC BY 4.0, 55,294,146-byte archive, provider MD5 verified. 930 images (418 crack, 512 no-crack), 930 SHA-256 identities, 237 distinct perceptual signatures. Local inventory: `/workspace/dataset-quarantine/tubers-20136698/inventory.json`.
- Filename grouping identified 18 recording families; 16 cross the supplied train/val/test boundaries. Do not reuse supplied splits. Rebuild splits by recording family and deduplicate against existing GCS media before inclusion. No-crack is not proof of NORMAL. Original annotations must remain available.
- Existing Sewer-ML v4 contains 101 verified IN-positive records. Candidate inventory: `/workspace/dataset-quarantine/acquisition-round/infiltration-candidates.jsonl`. These are acquisition candidates, not newly independent images or clean held-out examples: ancestor checkpoints already saw the images under the older label head.

## Missing-class status

- INFILTRATION: 101 existing IN-positive images, needs broader full-annotation retrieval and eligibility masks. Never mark records without a complete IN annotation as negative by default. Review active ingress semantics and family-level exposure before training/evaluation.
- OPEN_JOINT: no newly verified downloadable labeled media this round. Do not relabel FS displaced joint as open joint.
- PROTRUDING_LATERAL: no newly verified downloadable labeled media this round. AI-Hub LP is a relevant catalogue lead; registration/access and label terms require completion. GR branch pipe and PB drilled connection are not proof of intrusion.

## Source sweep

- Sewer-ML official archive FILELIST: HTTP 503 persists.
- Co-UDlabs: commercial reuse with attribution verified; labeled Drive folder HTTP 401; alternate folder returns no files. Repo contains no pipe sample media.
- Pipe-SOLO: supplied PMC11644997 is an inspection review, not verified Pipe-SOLO distribution. No relevant GitHub repository found in this query; this does not prove absence. Raw-media access remains unverified.
- Korea AI-Hub dataset 139: official catalogue reachable; approval/download flow remains necessary. Do not confuse its IN (Inside) with Sewer-ML IN (Infiltration).
- VideoPipe official repository Richard-61/VideoPipe: README supplies OpenDataLab link https://openxlab.org.cn/datasets/OpenDataLab/VideoPipe and competition access terms. No raw media downloaded in this round.
- UrbanPipe: repository searches produced no verified dataset distribution; unresolved.
- Wessex: previous official-page and direct-MPEG probes returned HTTP 403; no imported media.
- Roboflow segmentation project fyp-5vqpk/pipeline-defect-detection-segmentation: authenticated API still returns zero generated versions; CC BY 4.0; labels pipe/corrosion only.
- Roboflow kev-2du16/pipe-defects-2r7wj: API still exposes corrupted class names and zero Infiltration instances; keep excluded.
- SRuibo already acquired; alternate Hugging Face mirrors must be treated as possible duplicates, not dataset growth.
- MMKata sewerpipev2: 868 examples, roots/sediment/structural cracks; dataset card lacks explicit reuse terms. Not approved for training.
- ZhiyaYang sewer-defect-crack-dataset: public parquet inventory found; crack imagery cannot fill missing classes. Rights/provenance unresolved.
- SPARRKKK and abcli sewer dataset cards only declare a license; provenance/label semantics unresolved. No automatic remapping.
- Zenodo sewer search primarily returned reports and source-code archives rather than usable media. Corrosion/industrial-damage acquisition remains unresolved; catalogue results are not counted as images.

## Required training preparation

1. Consolidate full source annotations and add per-class annotation-availability masks; unknown classes must not become negative targets.
2. Correct semantic mappings: AF/BE deposits do not establish SURFACE_DAMAGE; FO obstacle does not establish GEOMETRY_UNCERTAIN; generic pipe class does not establish unreliable geometry. Preserve original codes and version mapping changes.
3. Verify perceptual hash implementation compatibility before comparing signatures; rerun hashes consistently. Exclude cross-source and near-duplicate families.
4. Quarantine SRuibo until label semantics and provenance pass review. Its prior inclusion must not be treated as approval.
5. Audit evaluation families against all ancestor checkpoint training manifests. Removing duplicates from a new manifest does not erase inherited exposure. Numeric filename blocks are proxies, not verified video IDs.
6. Establish an untouched development set. Previously reported scores remain exploratory where exposure or label coverage is uncertain.
7. Create a bounded continuation configuration with periodic checkpoint uploads, source sampling balance and per-class support reporting. Pin manifest and checkpoint SHA-256, preprocessing, seed, budget and timeout.
8. Evaluate all compatible candidates on identical supported records; tune fusion only on tuning data. Freeze the strongest preview candidate even if fusion adds no benefit. Do not use the final locked test during preparation.
9. Preview must expose unsupported classes and limited sample support, preserve zero-guessing measurement rejection, and remain research-scoped until rights are suitable.

No training or deployment was started during this acquisition round. The next cycle is training preparation with these gates, not an unqualified merge of all downloaded images.
