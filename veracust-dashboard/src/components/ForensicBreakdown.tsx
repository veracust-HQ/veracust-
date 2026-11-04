"use client";
import {useState} from "react";
import type {ForensicAnalysis} from "@/types";
import {Copy,Check,Database,Mic2,BrainCircuit,FileJson,AudioWaveform,GitMerge} from "lucide-react";
export default function ForensicBreakdown({analysis}:{analysis:ForensicAnalysis}){
 const [tab,setTab]=useState("digital");const [copied,setCopied]=useState(false);
 const e=analysis.evidence||{};const report=analysis.engineReport||{};const trace=(report.forensic_trace||{}) as Record<string,unknown>;
 const sections=[
  {id:"digital",label:"Digital integrity",Icon:Database,data:e.digitalFootprints||trace.check0||{}},
  {id:"bio",label:"Biological voice",Icon:Mic2,data:e.biologicalTelemetry||trace.biology||{}},
  {id:"physics",label:"Acoustic physics",Icon:AudioWaveform,data:trace.physics||{}},
  {id:"deep",label:"Neural model",Icon:BrainCircuit,data:e.deepLearning||trace.deep||{}},
  {id:"fusion",label:"Evidence fusion",Icon:GitMerge,data:{scores:report.scores||{},effective_weights:report.effective_weights||{},classification:report.classification,decision_limitations:report.limitations||[]}},
  {id:"json",label:"Full report",Icon:FileJson,data:report}
 ];
 const selected=sections.find(x=>x.id===tab)!;
 async function copy(){await navigator.clipboard.writeText(JSON.stringify(analysis,null,2));setCopied(true);setTimeout(()=>setCopied(false),1500)}
 return <section className="rounded-2xl border border-slate-800 bg-panel p-5">
  <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-sm font-semibold text-white">Forensic evidence breakdown</h2><p className="mt-1 text-[11px] text-slate-500">Inspect every evidence layer and the final fusion trace</p></div><button onClick={()=>void copy()} className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-2 text-[10px] text-slate-300">{copied?<Check size={13}/>:<Copy size={13}/>} {copied?"Copied":"Copy report"}</button></div>
  <div className="mb-4 flex flex-wrap gap-2">{sections.map(({id,label,Icon})=><button key={id} onClick={()=>setTab(id)} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[10px] ${tab===id?"bg-cyan-400/10 text-cyan-200":"bg-[#0a111b] text-slate-500 hover:text-slate-300"}`}><Icon size={13}/>{label}</button>)}</div>
  <div className="rounded-xl border border-slate-800 bg-[#080d15] p-4"><pre className="max-h-[440px] overflow-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-slate-300">{JSON.stringify(selected.data,null,2)}</pre></div>
 </section>
}
