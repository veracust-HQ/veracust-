# Veracust model training

Research starter for a pretrained WavLM encoder with a lightweight AASIST-inspired graph classifier. It is not a validated production detector.

## Manifest and split policy
Use manifest_template.csv. Labels are 0=bona fide and 1=synthetic. Required columns: path,label,speaker_id,generator,split,source,license. Split values are train, validation and test. Speakers must be disjoint across splits. Reserve at least one synthesis generator entirely for test; do not tune on that test set. Verify dataset cards, source papers, provenance, licence and consent/redistribution terms before use.

## Colab
1. Prepare the manifest and audio files in Colab or mounted Drive.
2. Run `python training/validate_manifest.py manifest.csv`.
3. Install `training/requirements-colab.txt`.
4. Run `python training/train_classifier.py --manifest manifest.csv --epochs 8 --batch-size 2`.
5. Save the checkpoint and metrics JSON to Drive; deploy only the inference checkpoint to the API host.

The script freezes the pretrained SSL encoder and trains the graph head. It reports ROC-AUC, EER estimate, balanced accuracy and confusion matrix; the operating threshold is selected on validation and reused unchanged on the held-out test split. It does not yet compute calibrated confidence intervals or a complete generator-wise benchmark.

Do not commit raw audio, datasets, credentials or model weights to Git. Store approved checkpoints in private artifact storage and configure VERACUST_CHECKPOINT on the inference service.
