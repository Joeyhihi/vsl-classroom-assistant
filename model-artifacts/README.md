# model-artifacts/

Local model files. **Everything here except this README is gitignored** — the repository is public.

Layout (from Phase 3/5):

```
model-artifacts/sign/<model_id>/
  model.onnx | templates.npz   # ONNX or .npz (allow_pickle=False); never pickle
  labels.json
  calibration.json             # temperature, threshold, margin, floor
  model_card.json              # versions, dataset hash, metrics, distribution scope, sha256 of each file
```

- Select a model with `VSL_SIGN_MODEL_ID=<model_id>` (no symlinks; they need admin rights on Windows).
- The backend verifies every sha256 in `model_card.json` before loading.
- Public distribution (GitHub Releases) only if **every** contributor in the training data consented to public model release; otherwise a private channel. See [docs/DATASET_AND_ANNOTATION.md](../docs/DATASET_AND_ANNOTATION.md#model-artifact-policy).
- **Never download or run models on the M1 development Mac** — real models are used on the Windows laptop only.
