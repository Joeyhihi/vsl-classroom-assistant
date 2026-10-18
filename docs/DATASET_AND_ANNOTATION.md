# Dataset & Annotation Strategy

> Data quality and how representative it is are the **biggest project risks**. The repository is **public**: no real data, landmarks, names, manifests, consent records, or identity registers ever go into git. Repo fixtures are **synthetic only**.

## 1. Roles (Track B0)

| Role | Responsibility |
|---|---|
| VSL lead reviewer | Approves vocabulary, the canonical sign for each item, and accepted variants; approves mirroring per item |
| VSL-fluent annotator(s), ≥1 besides the lead | Review samples; inter-annotator agreement |
| Deaf co-design participants | UX sessions: segmentation, confirmation, sign guide, literacy |
| Community partner | Recruitment, compensation, culturally appropriate consent |
| Developer (data controller) | Storage, security, deletion, identity register |

In the repo, people appear only as **role IDs** (e.g. `REV-01`), never by name.

## 2. Vocabulary

**Process:**
1. Draft a list of classroom intents.
2. Experts choose the canonical sign or phrase and its regional variants, and tag each item `unit_type`.
3. Experts review the `text_vi` wording, including how readable it is for low-literacy readers.
4. The item becomes `status: validated`.

The provisional intents are *not validated*: greeting, thank you, help, please repeat, slower please, I don't understand, question, yes, no, finished, toilet, water, wait.

Format of `ml/vocabulary/vocabulary.v1.yaml`:

```yaml
vocabulary_version: v1
items:
  - gloss_id: VSL_0003
    gloss: XIN_NHAC_LAI
    text_vi: "Xin nhắc lại"
    icon: repeat
    category: classroom_request
    unit_type: phrase          # sign | phrase
    variants: [{variant_id: A, note: "region-neutral"}]
    mirroring_ok: true
    status: validated          # provisional | validated
    reviewed_by: REV-01
    reviewed_at: 2027-01-15
distractors:                   # real VSL signs NOT in the vocabulary, used for rejection
  - distractor_id: DST_0001
    gloss: (expert-chosen)
```

There are about 2× as many distractor signs as vocabulary items. They are chosen by the experts, and the list includes signs that look similar to vocabulary items.

## 3. Consent (gate B2: no third-party recording before approval)

- **Adults only.** Written consent in Vietnamese, plus a **VSL explanation video** made by a fluent signer.
- **Separate, optional scopes**, each ticked independently:
  1. Landmark data for training and evaluation (required to take part).
  2. **Encrypted raw-video retention** (allows re-extraction later).
  3. **Reference clips** for the in-app sign guide.
  4. **Public model release**: a model trained with my data may be published.
  5. Portfolio or demo use of my clips.
- **The form states:**
  - who the data controller is (the developer) and how to contact them;
  - what is collected and where it is stored;
  - how long it is kept;
  - how to withdraw, and that withdrawn data is removed from future model releases, while already-published models are listed;
  - the compensation, agreed with the community partner.
- **Legal:** whether Vietnamese personal-data rules apply (Decree 13/2023/ND-CP, and the Personal Data Protection Law effective 2026) must be **reviewed, not assumed**. Biometric-like data such as face and hand landmarks may count as sensitive.
- **Identity register:** a table linking real contact details to `signer_id`, plus consent scopes and dates. It is **encrypted**, held only by the developer, stored **outside** `DATA_ROOT` and never in git. It exists only so withdrawal can be carried out.

## 4. Recording workflow

1. The session takes place in a controlled setting with **no bystanders**.
2. The developer enters the `consent_id` into the RecorderView. The red recording banner stays visible throughout.
3. The app prompts each item, shows a countdown, and captures it. The same browser extractor is used as for inference. Each session records:
   - target items, ≥5 repetitions each per signer;
   - distractor signs;
   - non-sign motion (scratching, adjusting glasses, idle, talking with the hands);
   - condition tags for lighting, background, camera, and distance.
4. Output goes to `DATA_ROOT/landmarks/<signer_id>/<session_id>/<sample_id>.npz` plus one manifest row. Raw `.webm` is saved **only** if scope 2 was ticked, and is encrypted.
5. The **realistic subset** is recorded in classroom-like conditions and belongs to the test set.

## 4a. Implementation (Phase 4, 2026-10-18)

- **Storage** (`vsl_features.dataset`): `DATA_ROOT/landmarks/<signer>/<session>/<sample>.npz` contains fixed-shape arrays with presence masks, no pickle. Files are written to a temp file and renamed, with Windows lock retries.
- **Append-only manifests:** `samples.jsonl`, `reviews.jsonl` and `tombstones.jsonl`. Nothing is rewritten. The current state is the sample row plus its latest review, with tombstoned samples excluded.
- **Consent rule, in code:** only `SELF` consent with a `DEV-..` signer ID, until B2 is approved (`VSL_THIRD_PARTY_RECORDING_ENABLED`). IDs must be pseudonymous. A `DATA_ROOT` inside a git checkout is refused.
- **Vocabulary:** `ml/vocabulary/vocabulary.dev.json` is a **placeholder, developer-only** list (DEV_01–03, DST_01 distractor, REST_DESK/LAP/DOWN and HOLD background). It is JSON rather than YAML, to avoid a dependency; the validated B1 vocabulary will use the same item fields.
- **Schema:** `ml/metadata/manifest.schema.json`, with a synthetic `manifest.example.jsonl`. A test keeps both in sync with `SampleRecord`.
- **Tools:** recorder v2 and the review view (web), `dataset_report.py`, `delete_recordings.py`, and `build_templates.py --from-manifest` (accepted targets only).

## 5. Manifest (JSONL, stored in `DATA_ROOT/manifests/`, never in git)

Fields: `sample_id, signer_id, session_id, gloss_id | distractor_id, variant_id, sample_kind (target|distractor|background), dominant_hand, signing_region (only with consent), lighting, background, camera, distance, fps, n_frames, image_w, image_h, feature_spec_version, extractor_version, extractor_backend, consent_id, consent_scopes, quality_flags, annotator_id, review_status (pending|accepted|rejected|relabelled), reject_reason, collected_at, dataset_version`.

The schema lives in `ml/metadata/manifest.schema.json`, and a **synthetic** example in `manifest.example.jsonl`.

## 6. Annotation

- Every sample is reviewed by a **VSL-fluent** annotator: accept, reject, or relabel.
- **Inter-annotator agreement** (Cohen's κ) is measured on ≥10% of samples by a second annotator.
- Rejection reasons come from a fixed list: wrong sign, incomplete, out of frame, tracking failure, other.

## 7. Splits, imbalance, size

- **Grouped by `signer_id`**, with no overlap. **≥3 test signers** are fixed early. Distractor identities are split too. A CI test checks for leakage.
- **Planning heuristic (approved):** **≥12 signers × ≥5 repetitions** per item. Signer count matters more than repetitions. Learning curves at G5 decide whether more data is needed.
- **Imbalance:** class-weighted loss and balanced sampling. Background and distractor classes are capped relative to targets.
- **Variation:**
  - **Regional:** variants share a `gloss_id`, and results are reported per region where `signing_region` is consented.
  - **Handedness:** mirroring augmentation is applied only for items with `mirroring_ok`.
  - **Conditions:** reported through the condition tags.

## 8. Versioning, storage, retention, deletion

- **Dataset version:** a semver tag plus the manifest sha256, recorded in every model card.
- **Storage:** `DATA_ROOT` lives **outside the repo**, by default under the platform user-data directory. This keeps data away from git and from AI coding tools indexing the repository.
  - Data stays on **the Windows laptop** by default, with disk encryption enabled where available (BitLocker or Device Encryption; to be verified for the edition installed). This follows from the rule that the M1 handles no real data or models.
  - Any copy is encrypted and logged.
- **Retention:** raw video is deleted right after extraction unless scope 2 was ticked. Landmarks are kept until the project ends or the contributor withdraws.
- **Withdrawal:**
  1. Look up the `signer_id` in the identity register.
  2. Run the deletion script, which removes the files and adds a tombstone to the manifest.
  3. Remove the contributor's samples from the next model release.
  4. Record the action in the register.
- **Public datasets:** none are assumed. Any external VSL dataset needs its licence and consent basis verified before use.

## 9. Model artifact policy {#model-artifact-policy}

- Artifacts are never committed (`model-artifacts/*` is gitignored).
- A model may be published on **public GitHub Releases only if every contributor in its training data ticked scope 4**. Otherwise it is shared through a private channel. `model_card.json` records `distribution: public | private`.
- Every artifact carries sha256 hashes that the backend verifies. ONNX or `.npz` only; no pickle.
