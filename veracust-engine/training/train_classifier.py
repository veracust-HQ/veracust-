from __future__ import annotations
import argparse, csv, json, random
from pathlib import Path
from typing import Any
import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score, balanced_accuracy_score, confusion_matrix, roc_curve

ENGINE = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ENGINE / "src"))
from ingestion.preprocessor import load_audio
from models.ssl_encoder import SSLEncoder
from models.aasist_l import AASISTL
from models.rawboost import RawBoost

class ManifestDataset(Dataset):
    def __init__(self, manifest: Path, split: str, seconds: float, augment: bool):
        with manifest.open(newline="", encoding="utf-8") as f:
            self.rows = [r for r in csv.DictReader(row for row in f if not row.lstrip().startswith("#"))
                         if r["split"].strip().lower() == split]
        if not self.rows: raise ValueError(f"No records for split={split!r}")
        self.base = manifest.resolve().parent
        self.max_samples = int(seconds * 16000)
        self.augment = augment
        self.rawboost = RawBoost(0.5 if augment else 0.0)
    def __len__(self): return len(self.rows)
    def __getitem__(self, index):
        row = self.rows[index]
        path = Path(row["path"].strip())
        if not path.is_absolute(): path = self.base / path
        wave = load_audio(path, target_sr=16000).waveform.squeeze(0).float()
        if wave.numel() > self.max_samples:
            start = random.randint(0, wave.numel()-self.max_samples) if self.augment else 0
            wave = wave[start:start+self.max_samples]
        if wave.numel() < self.max_samples: wave = nn.functional.pad(wave,(0,self.max_samples-wave.numel()))
        if self.augment: wave = self.rawboost(wave)
        return wave, torch.tensor(float(row["label"]),dtype=torch.float32)

def seed_all(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available(): torch.cuda.manual_seed_all(seed)

@torch.inference_mode()
def evaluate(ssl, model, loader, device, threshold=None):
    ssl.eval(); model.eval(); labels=[]; probs=[]
    for waves, targets in loader:
        p=torch.sigmoid(model(ssl(waves.to(device)))).cpu().numpy()
        labels.extend(targets.int().tolist()); probs.extend(p.tolist())
    y=np.asarray(labels); p=np.asarray(probs)
    if len(np.unique(y))<2: raise ValueError("Validation and test splits must contain both labels.")
    fpr,tpr,thresholds=roc_curve(y,p)
    eer_i=int(np.nanargmin(np.abs(fpr-(1-tpr))))
    if threshold is None:
        candidates=np.unique(np.concatenate(([0.0,0.5,1.0],p)))
        threshold=max(candidates,key=lambda t:balanced_accuracy_score(y,(p>=t).astype(int)))
    return {"count":int(len(y)),"roc_auc":float(roc_auc_score(y,p)),
      "eer_estimate":float((fpr[eer_i]+1-tpr[eer_i])/2),
      "threshold":float(threshold),
      "balanced_accuracy":float(balanced_accuracy_score(y,(p>=threshold).astype(int))),
      "confusion_matrix":confusion_matrix(y,(p>=threshold).astype(int)).tolist()}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--manifest",type=Path,required=True)
    ap.add_argument("--output",type=Path,default=Path("models/model_v1/classifier.pt"))
    ap.add_argument("--ssl-name",default="microsoft/wavlm-base-plus")
    ap.add_argument("--epochs",type=int,default=8);ap.add_argument("--batch-size",type=int,default=2)
    ap.add_argument("--lr",type=float,default=1e-4);ap.add_argument("--seconds",type=float,default=6)
    ap.add_argument("--seed",type=int,default=42);ap.add_argument("--device",default="cuda" if torch.cuda.is_available() else "cpu")
    a=ap.parse_args()
    if min(a.epochs,a.batch_size)<=0 or a.seconds<=0: raise SystemExit("epochs, batch size and seconds must be positive")
    seed_all(a.seed);device=torch.device(a.device)
    train=ManifestDataset(a.manifest,"train",a.seconds,True)
    val=ManifestDataset(a.manifest,"validation",a.seconds,False)
    test=ManifestDataset(a.manifest,"test",a.seconds,False)
    for name,ds in [("train",train),("validation",val),("test",test)]:
        if {int(r["label"]) for r in ds.rows}!={0,1}: raise ValueError(f"{name} split must contain bona fide and synthetic examples")
    train_loader=DataLoader(train,batch_size=a.batch_size,shuffle=True,num_workers=0)
    val_loader=DataLoader(val,batch_size=a.batch_size,shuffle=False,num_workers=0)
    test_loader=DataLoader(test,batch_size=a.batch_size,shuffle=False,num_workers=0)
    ssl=SSLEncoder(a.ssl_name,freeze=True).to(device).eval()
    model=AASISTL(ssl.hidden_size).to(device)
    y=[int(r["label"]) for r in train.rows];pos=max(1,sum(y));neg=max(1,len(y)-pos)
    loss_fn=nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg/pos,device=device))
    opt=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=1e-4)
    best=float("inf");best_state=None;history=[]
    for epoch in range(a.epochs):
        model.train();total=0.;count=0
        for waves,targets in train_loader:
            waves=waves.to(device);targets=targets.to(device);opt.zero_grad(set_to_none=True)
            with torch.no_grad(): feats=ssl(waves)
            loss=loss_fn(model(feats),targets);loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(),3.0);opt.step()
            total+=float(loss.item())*targets.numel();count+=targets.numel()
        model.eval();vl=0.;vc=0
        with torch.inference_mode():
            for waves,targets in val_loader:
                waves=waves.to(device);targets=targets.to(device);vl+=float(loss_fn(model(ssl(waves)),targets).item())*targets.numel();vc+=targets.numel()
        vloss=vl/max(vc,1);history.append({"epoch":epoch+1,"train_loss":total/max(count,1),"validation_loss":vloss})
        print(f"epoch {epoch+1}/{a.epochs}: train={total/max(count,1):.5f} validation={vloss:.5f}")
        if vloss<best: best=vloss;best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    if best_state is None: raise RuntimeError("No model checkpoint was produced")
    model.load_state_dict(best_state)
    vm=evaluate(ssl,model,val_loader,device)
    tm=evaluate(ssl,model,test_loader,device,vm["threshold"])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    torch.save({"model":best_state,"ssl_name":a.ssl_name,"input_dim":ssl.hidden_size,
      "seed":a.seed,"sample_rate":16000,"max_seconds":a.seconds,
      "validation_threshold":vm["threshold"],"validation_metrics":vm,
      "unseen_test_metrics":tm,"training_history":history,"model_version":"veracust-model-v1"},a.output)
    a.output.with_suffix(".metrics.json").write_text(json.dumps({"validation":vm,"unseen_test":tm,"history":history},indent=2),encoding="utf-8")
    print(f"Saved {a.output}; held-out generator test metrics: {tm}")
if __name__=="__main__": main()
