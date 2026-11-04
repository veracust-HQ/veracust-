# Veracust v1 — API-First Dataset Access (English, Balanced)

This document supersedes the archive-first acquisition instructions in `docs/TRAINING_PLAN_V1.md` for the first experiment.

## The important distinction

We want to avoid manually downloading and extracting complete ZIP archives. Hugging Face Datasets supports `streaming=True`: rows and audio are fetched as the iterator consumes them. Audio bytes still travel to the Colab runtime for decoding and model training; this is not remote GPU training and it is not zero network transfer. The dataset library may also cache files unless configured otherwise.

## Source access status

| Source | API/streaming path | v1 use | Caveat |
|---|---|---|---|
| ODSS | Hugging Face Datasets: `SpeechAntiSpoofingBenchmarks/ODSS` | Primary train/validation candidate | Community-maintained packaging of ODSS; inspect card, metadata and licence. CC BY-SA 4.0. |
| In-the-Wild | Hugging Face Datasets: `mueller91/In-The-Wild` | External evaluation only | Hub card metadata currently reports CC BY-SA 4.0, while the original dataset page has been described as Apache 2.0. Treat this as a licence discrepancy; do not use commercially or redistribute until verified against the exact release's licence. |
| ASVspoof 2021 LA | Official release is on Zenodo, with keys/metadata on ASVspoof site | Optional later held-out benchmark | The official release is an archive-based distribution; an official streaming dataset API was not verified. Zenodo API can expose metadata, but audio still needs retrieval. Do not claim API streaming support. |

References:
- ODSS Hub dataset card: https://huggingface.co/datasets/SpeechAntiSpoofingBenchmarks/ODSS
- ODSS official project page: https://www.idmt.fraunhofer.de/en/publications/datasets/ODSS-open-dataset-synthetic-speech.html
- In-the-Wild Hub dataset card: https://huggingface.co/datasets/mueller91/In-The-Wild
- In-the-Wild original paper: https://arxiv.org/abs/2203.16263
- ASVspoof official release page: https://www.asvspoof.org/index2021.html
- Hugging Face streaming documentation: https://huggingface.co/docs/datasets/stream

## Colab streaming proof-of-access

Start with ODSS only. This is a small smoke test: inspect metadata and stream a few English examples before any long run.

```python
!pip -q install -U datasets[audio] huggingface_hub soundfile

from datasets import load_dataset
from itertools import islice

odss = load_dataset(
    "SpeechAntiSpoofingBenchmarks/ODSS",
    split="test",
    streaming=True,
)

for row in islice(iter(odss), 3):
    print(row.keys())
    print("label:", row.get("label"))
    print("path:", row.get("path"))
    print("notes:", row.get("notes"))
    audio = row.get("audio")
    if audio:
        print("audio metadata:", {k: v for k, v in audio.items() if k != "array"})
```

The ODSS card describes English, German and Spanish. It reports the `notes` field as JSON containing language, speaker and generator. Filter English using that metadata; do not assume the stream is English-only. Inspect the actual returned schema before building the adapter.

## Stream audio into the existing training pipeline

The current repository trainer expects a local CSV manifest and local audio paths. It does not currently accept a Hugging Face streaming iterator. Therefore the safe first implementation is a small **bounded staging cache**:

1. Stream ODSS rows.
2. Parse language, speaker, generator and class label from the row metadata.
3. Keep English rows only.
4. Assign speaker-disjoint train/validation groups; keep generator holdout policy explicit.
5. Decode each selected audio row and write only the selected clips into a bounded Colab temporary directory (or a small Drive cache if persistence is needed).
6. Write the existing manifest columns: `path,label,speaker_id,generator,split,source,license`.
7. Run the existing `training/validate_manifest.py`.
8. Run the unchanged `training/train_classifier.py`.

This is still audio transfer, but it avoids downloading the complete archive and keeps only selected clips. The runtime cache is disposable. The manifest and model outputs can be saved to Drive.

### Example row inspection / metadata parser

The exact `notes` structure must be checked against live rows before relying on this parser:

```python
import json

def parse_odss_notes(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}

# Example after inspecting a row:
meta = parse_odss_notes(row.get("notes"))
language = str(meta.get("language", "")).lower()
speaker = meta.get("speaker")
generator = meta.get("generator") or meta.get("attack")
```

Do not invent missing speaker IDs or generator labels. If metadata is incomplete, skip those rows until the adapter can map them reliably.

## Important limitation: streaming vs training

The current trainer uses a map-style PyTorch Dataset that reads audio paths and shuffles training samples. It cannot consume a remote iterable directly without an architectural change. The bounded staging cache lets us keep the model and trainer unchanged for v1. A future streaming-native trainer could use an IterableDataset, but that is not needed to prove the API-first workflow.

## In-the-Wild external evaluation

After the ODSS model is trained and frozen, evaluate on a separate In-the-Wild stream. Do not train on it or tune the threshold using it. Verify the exact Hub release's label mapping, speaker IDs and licence first. Its original dataset is English and contains real and synthetic recordings; keep results separate from the training benchmark.

Example access probe:

```python
wild = load_dataset(
    "mueller91/In-The-Wild",
    split="train",
    streaming=True,
)
first = next(iter(wild))
print(first.keys())
print(first)
```

If the repository uses a different split name, inspect the dataset card and available splits rather than guessing. The code above is an access probe, not a guaranteed split name.

## ASVspoof decision

Do not block the first API-first experiment on ASVspoof. The official ASVspoof 2021 LA release is archive-based. We can use its official Zenodo API for record metadata and download only selected files if the licence/protocol and file structure permit, but it is not currently a verified row-streaming audio dataset source. Add it as a later benchmark or use a clearly identified Hub mirror only after validating provenance, labels, licence and metadata.

## What must be implemented in the repository

- A Colab notebook or script such as `training/colab_stream_odss.ipynb` that performs the bounded staging workflow.
- Dataset-card schema checks that fail loudly if fields/splits change.
- English-only filtering and stable speaker/generator mapping.
- Deterministic speaker-disjoint split assignment and a documented generator holdout.
- Audio decode/resample to 16 kHz mono, matching the existing trainer.
- A maximum clip count / disk budget so a Colab session cannot unexpectedly fill its storage.
- A manifest audit report: counts by split, label, speaker and generator, plus duration and missing metadata.
- No dataset audio committed to GitHub. Do not store Hugging Face tokens in notebook cells; use Colab Secrets only if a gated source requires authentication.

## Acceptance test before full training

- [ ] ODSS streaming iterator opens in Colab without downloading the full archive.
- [ ] A handful of English audio rows decode successfully.
- [ ] Labels map correctly to 0 bona fide / 1 synthetic.
- [ ] Speaker and generator metadata are present and normalized.
- [ ] Bounded staging produces a valid existing-format manifest.
- [ ] Existing validator passes.
- [ ] Existing trainer runs on a small smoke subset before scaling up.
