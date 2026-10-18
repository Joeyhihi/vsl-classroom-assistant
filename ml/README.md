# ml/ (vsl-ml)

Phase 5 training, evaluation, calibration and ONNX export. **Training runs on the Windows laptop
and in the CI ML smoke job only — never on the M1 Mac.**

| Path | What |
|---|---|
| `src/vsl_ml/data.py` | Reviewed manifest samples (or the synthetic signer) → examples, trimmed by the live segmenter |
| `src/vsl_ml/splits.py` | Grouped splits (signer > session > sample), distractor-identity split, leakage check |
| `src/vsl_ml/augment.py` | Speed change, frame drops, noise on present parts (no mirroring until B1) |
| `src/vsl_ml/calibration.py` | Temperature scaling, operating point (FAR and confident-wrong ≤ target) |
| `src/vsl_ml/metrics.py` | Macro-F1 + bootstrap CI, top-3, FAR, coverage, ECE, per-signer, confusion |
| `src/vsl_ml/template.py` | DTW template baseline, scored like the neural models |
| `src/vsl_ml/torch_models.py` | GRU / TCN, training loop, ONNX export (needs the `train` extra) |
| `vocabulary/`, `metadata/` | Dev vocabulary and the manifest schema |
| `datasets/` | Always empty: data lives in `DATA_ROOT`, outside the repo |

Everything except `torch_models.py` is NumPy only and unit-tested on the Mac.

```powershell
uv run --extra train python scripts/train_sign_model.py --model-id vsl-01
```

See [docs/AI_ML_STRATEGY.md](../docs/AI_ML_STRATEGY.md) §2b, and docs/CROSS_PLATFORM_SETUP.md §8c for the workflow.
