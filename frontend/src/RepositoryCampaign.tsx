import { useEffect, useState } from "react";

type Row = {case:string;role:string;trial:number;run_id:string;ordinary:string;independent:string;classification:string;assessment?:{explanation:string}};
type Campaign = {campaign_sha256:string;scope:string;limitations:string[];counts:{genuine_candidates_executed:number;selected_candidates:number;candidate_audits:number;planned_candidate_audits:number;repeat_disagreements:number;candidate_outcomes:Record<string,number>};cases:{key:string;repository:string;revision:string;provenance:{reference:string};requirement:{statement:string};assessment?:{classification:string;explanation:string}}[];rows:Row[]};

export default function RepositoryCampaign({onOpen,onSelect,disabled}:{onOpen:(id:string)=>void;onSelect:()=>void;disabled:boolean}) {
  const [campaign,setCampaign]=useState<Campaign|null>(null),[selected,setSelected]=useState(""),[error,setError]=useState("");
  useEffect(()=>{let disposed=false;(async()=>{const response=await fetch("/api/repository-audits/campaigns/g3");if(response.status===404)return;if(!response.ok)throw Error("Campaign evidence could not be validated.");const value=await response.json() as Campaign;if(!disposed){setCampaign(value);setSelected(value.cases[0]?.key??"");}})().catch(e=>{if(!disposed)setError(String(e));});return()=>{disposed=true;};},[]);
  if(error)return <p role="alert">{error}</p>;
  if(!campaign)return null;
  const current=campaign.cases.find(c=>c.key===selected), rows=campaign.rows.filter(r=>r.case===selected);
  return <section className="evaluation-panel audit-import" aria-label="G3 real change campaign">
    <h2>G3 · real software changes</h2><p>{campaign.scope}</p>
    <p><strong>{campaign.counts.genuine_candidates_executed} / {campaign.counts.selected_candidates} genuine candidates formally evaluated</strong>{" · "}{campaign.counts.candidate_audits} / {campaign.counts.planned_candidate_audits} planned audits{" · "}{campaign.counts.repeat_disagreements} repeat disagreements</p>
    <ul>{Object.entries(campaign.counts.candidate_outcomes).map(([key,value])=><li key={key}>{key.replaceAll("_"," ")}: {value} / {campaign.counts.selected_candidates} candidates</li>)}</ul>
    <label>Campaign candidate<select aria-label="Campaign candidate" value={selected} disabled={disabled} onChange={e=>{setSelected(e.target.value);onSelect();}}>{campaign.cases.map(c=><option key={c.key} value={c.key}>{c.repository} · {c.key}</option>)}</select></label>
    {current&&<><h3>{current.key}</h3><p>{current.requirement.statement}</p><p><a href={current.provenance.reference} target="_blank" rel="noreferrer">Original upstream change</a>{" · "}<code>{current.revision}</code></p></>}
    <p>Retained evidence of fresh local executions. References overlap the scored upstream patches; alternatives are authored controls. Repeated runs are separate executions of the same candidate.</p>
    <div className="comparison-table-wrap"><table className="comparison-table"><thead><tr><th>Role / trial</th><th>Ordinary</th><th>Independent</th><th>Interpretation</th><th>Evidence</th></tr></thead><tbody>{rows.map(r=><tr key={r.run_id}><td>{r.role.replaceAll("_"," ")} · {r.trial}</td><td>{r.ordinary.replaceAll("_"," ")}</td><td>{r.independent.replaceAll("_"," ")}</td><td>{r.classification.replaceAll("_"," ")}</td><td><button disabled={disabled} onClick={()=>onOpen(r.run_id)}>Inspect {r.role.replaceAll("_"," ")} {r.trial}</button></td></tr>)}</tbody></table></div>
    {current?.assessment&&<p>{current.assessment.explanation}</p>}
    {!rows.length&&<p>No admitted execution evidence for this candidate.</p>}
    <details><summary>Campaign scope and limitations</summary><ul>{campaign.limitations.map(l=><li key={l}>{l}</li>)}</ul><p>Frozen declaration SHA-256 <code>{campaign.campaign_sha256}</code></p></details>
  </section>;
}
