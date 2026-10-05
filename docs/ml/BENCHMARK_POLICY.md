# External Benchmark Isolation & Feedback Policy

## 1. Core Principles & Legal Invariants

JointInspect maintains a strict firewall between **production training pipelines** and **external benchmark evaluation datasets** (such as Sewer-ML).

### Status of Sewer-ML:
- **`SEWERML_STATUS = BENCHMARK_PERMISSION_PENDING`**
- **`production_eligible = false`**
- **`training_allowed = false`**

Under no circumstances may Sewer-ML or any academic/restricted-license dataset be used for:
- Production training
- Supervised fine-tuning
- Self-supervised pretraining
- Knowledge distillation
- Production RAG knowledge base items
- Vector embeddings in production
- Production model weights
- Synthetic-data derivation

---

## 2. Benchmark Isolation Architecture

When permission is granted to run an external benchmark, evaluation operates under **strict read-only isolation**:

```mermaid
flowchart TD
    A[Frozen Production Model] --> B[Benchmark Evaluator]
    C[External Benchmark Images] --> B
    B --> D[Predictions / Inferences]
    D --> E[Benchmark Metrics Only]
    
    subgraph Strictly Prohibited
        C -.x F[Training Batches]
        C -.x G[Knowledge Distillation]
        C -.x H[Production RAG]
        C -.x I[Visual Embeddings]
    end
```

### Execution Invariants:
1. **Frozen Weights**: Optimizer and backward-pass calculation are disabled (`inference-only`).
2. **No Weight Mutation**: Model binary checksums are verified before and after evaluation to guarantee immutability.
3. **No Training Leaks**: No benchmark sample may ever enter a production manifest or training batch.
4. **No Embeddings / RAG**: Benchmark images and labels are excluded from all vector databases and runtime advisory corpora.

---

## 3. Benchmark Feedback Policy (Weakness Remediation)

When benchmark evaluation reveals a model weakness (e.g., lower accuracy on off-axis joints with turbid water reflections):

### Permitted Response:
- Analyze the geometric or optical failure mode conceptually.
- **Collect or generate OUR OWN commercially eligible assets**:
  - Program our parametric synthetic generator to render off-axis joints with turbid reflections (`training/synthetic/generator.py`).
  - Capture controlled footage on our physical test rig (`docs/ml/PHYSICAL_TEST_RIG.md`).
  - Ingest customer/partner footage under written commercial training agreements.

### Strictly Prohibited Response:
- **NEVER** copy benchmark images into training sets.
- **NEVER** fine-tune or train on benchmark samples.
- **NEVER** use benchmark labels as pseudo-ground truth.
