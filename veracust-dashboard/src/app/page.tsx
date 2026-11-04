"use client";

import { useState } from "react";

type Analysis = {
  id?: string; verdict?: string; riskLevel?: string; confidence?: number;
  manipulationProbability?: number; latencyMs?: number; audioSaved?: boolean;
  evidence?: Record<string, unknown>; engineReport?: Record<string, unknown>;
};

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [usage, setUsage] = useState<{creditsRemaining?: number | null; unlimited?: boolean} | null>(null);

  async function runAnalysis() {
    if (!file) return;
    setBusy(true); setError(""); setAnalysis(null);
    try {
      const form = new FormData(); form.append("file", file);
      const res = await fetch("/api/v1/detect", { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "Analysis failed.");
      setAnalysis(data.analysis); setUsage(data.usage || null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not complete analysis.");
    } finally { setBusy(false); }
  }

  return <main className="shell">
    <header className="top"><div className="brand"><span className="mark">V</span><div><b>VERACUST</b><small>VOICE AUTHENTICITY INTELLIGENCE</small></div></div><span className="status">ENGINE CONNECTED VIA API</span></header>
    <section className="hero"><p className="eyebrow">AUDIO FORENSICS / WORKBENCH</p><h1>Is this voice <em>authentic?</em></h1><p className="sub">Inspect digital, acoustic, biological and neural evidence in one forensic workflow.</p></section>
    <section className="panel"><div><p className="eyebrow">01 / SUBMIT AUDIO</p><h2>Upload a recording</h2><p className="muted">WAV, MP3, M4A or FLAC · 50 MB maximum. Uploaded audio is processed temporarily and deleted after analysis.</p></div>
      <label className="drop"><input type="file" accept=".wav,.mp3,.m4a,.flac,audio/*" onChange={e=>{setFile(e.target.files?.[0] || null);setAnalysis(null);setError("");}}/><span className="upload">↑</span><b>{file ? file.name : "Choose an audio file"}</b><small>{file ? (file.size/1024/1024).toFixed(2)+" MB" : "Select a file to begin forensic analysis"}</small></label>
      <button onClick={runAnalysis} disabled={!file || busy}>{busy ? "ANALYZING…" : "RUN FORENSIC ANALYSIS →"}</button>
      {error && <p className="error">{error}</p>}
    </section>
    {analysis && <section className="panel result"><div className="resulthead"><div><p className="eyebrow">02 / ANALYSIS VERDICT</p><h2>{analysis.verdict === "synthetic" ? "Potential synthetic audio" : "No synthetic classification raised"}</h2><p className="muted">This is an experimental forensic assessment, not proof of speaker identity or authenticity.</p></div><div className="score"><strong>{analysis.manipulationProbability ?? analysis.confidence ?? "—"}%</strong><small>MODEL / FUSION SCORE</small></div></div>
      <div className="metrics"><div><small>RISK LEVEL</small><b>{analysis.riskLevel || "—"}</b></div><div><small>PROCESSING</small><b>{analysis.latencyMs ?? "—"} ms</b></div><div><small>AUDIO RETAINED</small><b>{analysis.audioSaved ? "Yes" : "No"}</b></div><div><small>CREDITS LEFT</small><b>{usage?.unlimited ? "Unlimited" : usage?.creditsRemaining ?? "—"}</b></div></div>
      <h3>Forensic evidence trace</h3><pre>{JSON.stringify(analysis.evidence || analysis.engineReport?.forensic_trace || {}, null, 2)}</pre>
      <details><summary>Full engine report</summary><pre>{JSON.stringify(analysis.engineReport || {}, null, 2)}</pre></details>
    </section>}
    <footer>VERACUST · EXPERIMENTAL DETECTION · RESULTS REQUIRE INDEPENDENT VALIDATION</footer>
  </main>;
}
