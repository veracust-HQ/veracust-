# Veracust Model v1 — Dataset Acquisition & Colab Training Plan

**Target:** balanced binary synthetic-speech triage, English only  
**Model already in repository:** frozen `microsoft/wavlm-base-plus` encoder + lightweight AASIST-inspired graph classifier  
**Training entry point:** `veracust-engine/training/train_classifier.py`  
**Manifest validator:** `veracust-engine/training/validate_manifest.py`

This plan reuses the existing pipeline. It does not replace the model architecture, change production, or require a paid GPU. Run the first experiment in Google Colab with a free GPU when available.

## 1. What “balanced” means for v1

- Optimize for balanced accuracy and ROC-AUC, not maximum synthetic recall alone.
- Track false negatives (synthetic classified as bona fide) and false positives (genuine classified as synthetic) separately.
- Keep genuine and synthetic examples represented in every split.
- Hold out speakers across splits and hold out at least one synthetic generator family for the final test.
- Do not call a score a calibrated probability until calibration has been measured on independent data.
- A borderline result should eventually be reported as inconclusive rather than forced into a confident label. That production behavior is a separate integration task after model evaluation.

## 2. Dataset acquisition order

### A. ODSS — primary starter corpus

- Official record: https://zenodo.org/records/8370669
- Download: `odss.zip` (2.4 GB according to the record).
- Contains natural and synthetic speech; the record describes it as multilingual and multispeaker. Use English rows only for this experiment.
- Licence: CC BY-SA 4.0. Preserve attribution and review ShareAlike obligations before redistributing derivatives, model weights, or a bundled dataset.
- The Hugging Face packaging documents 26,954 clips, including 7,961 bona-fide and 18,993 spoof clips, and identifies English examples. Verify the actual downloaded release and metadata rather than assuming every mirror has identical contents.

**Use:** training and validation source. Keep the ODSS speaker identities disjoint between train and validation. Do not randomly split clips from the same speaker across partitions.

### B. ASVspoof 2021 Logical Access — held-out robustness evaluation

- Official evaluation-plan page: https://www.asvspoof.org/index2021.html
- LA evaluation archive record: https://zenodo.org/records/4837263
- The evaluation archive is about 7.8 GB and requires registration/approval according to the evaluation plan. The original task data is FLAC at 16 kHz.
- The ASVspoof 2021 evaluation plan identifies the database under the Open Data Commons Attribution (ODC-By) licence. Keep the licence and attribution files with the downloaded data.
- LA includes spoofed speech and transmission/codec conditions. It is not a drop-in replacement for a training split: use its evaluation partition as a final held-out test, subject to the dataset's official protocol and access terms.

**Use:** final test only. Map the protocol's speaker and attack metadata into the manifest. Ensure synthetic generator/attack identifiers used in test do not overlap training/validation identifiers. Do not tune thresholds against this test set.

### C. In-the-Wild — external reality check, not training data

- Dataset information/download: https://www.deepfake-total.com/in_the_wild
- Paper: https://arxiv.org/abs/2203.16263
- Approximately 37.9 hours, including roughly 20.7 hours genuine and 17.2 hours fake, from public online recordings of 58 public figures.
- The dataset page states Apache License 2.0. Keep the supplied licence and attribution with the files; verify the downloaded package metadata.
  
**Use:** untouched external evaluation after the model and threshold are frozen. This set is particularly useful for exposing domain shift from studio/lab data to real online recordings. Do not mix it into training or use it to tune the v1 threshold.

### Licence and data-handling gate

Before downloading, create a local `DATASET_SOURCES.md` record with source URL, access date, version/release, checksum, licence text, attribution, and intended use. Do not commit audio, archives, private download credentials, or personal tokens to GitHub. Store data and checkpoints in the user's Google Drive. Do not redistribute any source audio. If the model will be commercialized or weights distributed, have the dataset licence obligations reviewed first—especially ODSS ShareAlike.

## 3. Manifest contract already enforced by the repository

The current validator requires these exact CSV columns:

```csv
path,label,speaker_id,generator,split,source,license
```

- `label=0`: bona fide / genuine human speech.
- `label=1`: synthetic / spoof speech.
- `speaker_id`: stable speaker identity from source metadata. Prefix IDs by dataset/source to avoid collisions, e.g. `odss:vctk:p293`.
- `generator`: actual TTS/VC/attack family for synthetic items. For genuine items use a stable value such as `human`; do not use this placeholder for synthetic rows.
- `split`: exactly `train`, `validation`, or `test`.
- `source`: dataset name and release.
- `license`: licence identifier, e.g. `CC-BY-SA-4.0` or `ODC-By`.

Paths may be absolute or relative to the manifest's directory. Prefer relative paths within a Drive dataset root so the manifest remains portable.

### Split policy

1. ODSS English speakers: assign speaker groups to train or validation only; no speaker may appear in both.
2. ASVspoof 2021 LA: reserve official evaluation data for test. Keep its speaker IDs and attack/generator IDs distinct from training/validation.
3. In-the-Wild: keep outside the training manifest initially; build a separate external-evaluation manifest only after the checkpoint is frozen.
4. Make sure each of train, validation, and test has both labels. The repository validator checks this.
5. The validator checks speaker leakage and synthetic generator overlap between train/validation and test. It does not validate dataset licence, language, duplicate audio, class balance, or the correctness of metadata; those need a separate audit.

**Important data caveat:** The current validator's generator holdout check compares literal `generator` strings. Normalize generator names consistently, and use meaningful attack-family names rather than generic values such as `spoof`. If the source metadata cannot identify a generator, mark it unknown and keep that subset out of claims about unseen-generator generalization.

## 4. Google Colab runbook (existing scripts)

### Step 1 — start a GPU runtime

In Colab choose **Runtime → Change runtime type → T4 GPU** (or another available GPU). GPU availability is not guaranteed on the free tier. Do not purchase compute or upgrade a plan for this first run.

### Step 2 — mount Drive and clone the existing repository

```python
from google.colab import drive
drive.mount("/content/drive")

!git clone https://github.com/veracust-HQ/veracust-.git /content/veracust
%cd /content/veracust
```

For a private repository, use Colab's GitHub integration or a short-lived credential stored in Colab Secrets; never paste a GitHub token into a notebook cell or commit it.

### Step 3 — install dependencies without replacing Colab's CUDA PyTorch

First inspect the runtime:

```python
import torch
print("torch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none")
```

Then install the repository's Colab requirements, but preserve a working Colab torch/torchaudio CUDA pair. If torch is already CUDA-enabled, do not blindly reinstall it from PyPI.

```python
%cd /content/veracust/veracust-engine
!pip install -r training/requirements-colab.txt
```

If dependency resolution attempts to replace the CUDA build, stop and install only the missing packages (transformers, numpy, pandas, scikit-learn, soundfile) instead.

### Step 4 — place datasets in Drive

Suggested layout:

```text
/content/drive/MyDrive/veracust-data/
  raw/
    odss/
    asvspoof2021_la/
    in_the_wild/
  processed/
    audio/
    manifest_v1.csv
    external_in_the_wild.csv
  runs/
    model_v1/
```

Download/extract each dataset according to its official instructions. Keep the original archives and licence/attribution files. Do not upload audio to the Git repository.

### Step 5 — create and audit the manifest

Create `processed/manifest_v1.csv` from the source metadata. Convert paths to Drive-relative paths where possible. Keep only English ODSS items. Map the official ASVspoof LA evaluation labels and metadata to the test split. Do not guess missing speakers or generator IDs.

Run the existing validator:

```bash
python training/validate_manifest.py /content/drive/MyDrive/veracust-data/processed/manifest_v1.csv
```

If it fails, fix the manifest—not the validator's safeguards. Before training, also inspect counts by split/label, speaker counts, generator counts, language, duration, duplicate paths, and licence coverage.

### Step 6 — run the existing training script

Start with the repository defaults (8 epochs, batch size 2, 6-second crop, learning rate 1e-4). Save output to Drive so it survives a Colab reset:

```bash
python training/train_classifier.py \
  --manifest /content/drive/MyDrive/veracust-data/processed/manifest_v1.csv \
  --output /content/drive/MyDrive/veracust-data/runs/model_v1/classifier.pt \
  --epochs 8 --batch-size 2 --seconds 6 --lr 1e-4 --seed 42
```

The script freezes WavLM and trains the lightweight graph head. It selects the best epoch by validation loss, chooses a validation balanced-accuracy threshold, and writes a checkpoint plus a `.metrics.json` report. If the GPU runs out of memory, first reduce batch size to 1; do not change the architecture or training data split just to get a run to finish.

### Step 7 — evaluate without threshold leakage

- Record validation ROC-AUC, EER estimate, balanced accuracy, and confusion matrix.
- The script evaluates the held-out test set using the threshold selected on validation. Do not select a new threshold using test results.
- Report false-negative rate (synthetic predicted bona fide) and false-positive rate (genuine predicted synthetic) explicitly.
- Evaluate the untouched In-the-Wild set separately after training.
- Save the exact manifest, source/licence register, commit SHA, runtime versions, seed, checkpoint, metrics JSON, and logs in the Drive run folder.

## 5. Important repository integration gaps to fix before production

These are visible in the current code and are not solved by training alone:

1. `train_classifier.py` saves `validation_threshold` and metrics in the checkpoint. `src/pipeline.py` currently loads only `state["model"]`; it does not read the saved threshold.
2. `src/fusion/dynamic_fusion.py` currently applies the default fusion threshold (0.50) to a heuristic + model mixture. The classifier's validation threshold is on the classifier probability scale; it must **not** be copied directly onto the fused score.
3. Without a trained checkpoint, the current pipeline can still return `bona_fide` or `synthetic` based on heuristic fusion. That is not a defensible trained-model verdict. Production should return an explicit `inconclusive` / `model_unavailable` state until a validated checkpoint is configured.
4. The training script evaluates the test set but does not currently save per-clip predictions or a detailed per-generator report. Add those before making generalization claims.
5. The current `evaluate()` threshold selection maximizes balanced accuracy on validation. This is a reasonable first balanced baseline, but threshold stability and confidence intervals should be checked before production.

Do not deploy the checkpoint until the inference path, threshold semantics, API response schema, and dashboard verdict card are updated and tested together.

## 6. v1 acceptance checklist

- [ ] Dataset source, release, checksum, licence, and attribution recorded.
- [ ] English-only subset verified.
- [ ] Train/validation/test all contain both classes.
- [ ] Speaker IDs are disjoint across splits.
- [ ] Synthetic generator/attack IDs are held out from train/validation for test.
- [ ] Duplicate files and corrupted audio checked.
- [ ] Validation threshold selected without looking at test results.
- [ ] ROC-AUC, EER, balanced accuracy, confusion matrix, false-negative rate, and false-positive rate reported.
- [ ] External In-the-Wild results reported separately.
- [ ] Checkpoint and metrics saved in Drive; no audio or secrets committed to Git.
- [ ] Production integration and API/dashboard tests pass before enabling model verdicts.

## 7. References

- ASVspoof 2021: https://www.asvspoof.org/index2021.html
- ASVspoof 2021 evaluation plan: https://www.asvspoof.org/asvspoof2021/asvspoof2021_evaluation_plan.pdf
- ASVspoof 2021 LA Zenodo record: https://zenodo.org/records/4837263
- ODSS Zenodo record: https://zenodo.org/records/8370669
- ODSS Fraunhofer project page: https://www.idmt.fraunhofer.de/en/publications/datasets/ODSS-open-dataset-synthetic-speech.html
- In-the-Wild dataset page: https://www.deepfake-total.com/in_the_wild
- In-the-Wild paper: https://arxiv.org/abs/2203.16263
