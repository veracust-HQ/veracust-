# Veracust model training

The initial target is a pretrained WavLM/Wav2Vec2 encoder with a lightweight binary classifier. This is a research starter, not a validated production model.

## Dataset manifest

Use `manifest_template.csv`. Labels: `0 = bona fide`, `1 = synthetic`. Every row must identify a speaker, source dataset, licence and (for synthetic examples) generator. Do not mix speakers across train/validation/test. To measure generator generalization, reserve one or more synthesis systems entirely for the final test split.

Initial data target: 100–200 speakers, with multiple bona-fide and synthetic recordings per speaker where ethically and legally permitted. Balance speakers and classes; avoid letting one generator or one source dataset dominate.

## Evaluation requirements

Report at minimum: class-wise precision/recall/F1, ROC-AUC, EER, confusion matrix, calibration error, false-positive rate at the selected operating point, and performance broken down by generator, speaker, codec, duration and language/accent where sample sizes support it. Keep an unseen-generator test set sealed until model selection is complete.

## Colab workflow

1. Verify dataset cards, source papers, licences and redistribution/derivative-work terms.
2. Prepare a local or mounted manifest and run `python validate_manifest.py manifest.csv`.
3. Install `requirements-colab.txt`, train from a pretrained checkpoint and save model weights, configuration, dataset manifest hash and metrics to Drive.
4. Evaluate with speaker- and generator-disjoint splits.
5. Export a versioned checkpoint and metadata; deploy inference only (never train on the Render web service).

Do not commit datasets, raw audio, access tokens or model weights to Git. Store approved checkpoints in private artifact storage and record a checksum/version in the deployment configuration.
