import { useEffect, useRef, useState } from "react";
import { api } from "./types";

export type IndependentApproval = {verification_id:string; validation_run_id:string; approve_independent_plan:true};
type Props = {snapshotId:string; candidateId:string; candidateHash:string; ordinaryPlanId:string; runtime:string; imageId:string; disabled:boolean; onChange:(value:IndependentApproval|null)=>void; onBusy:(value:boolean)=>void};
const words=(s:string)=>s.replaceAll("_"," ");
const hex = async (s:string) => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s))),b=>b.toString(16).padStart(2,"0")).join("");

export default function IndependentPlan(p:Props) {
  const [requirements,setRequirements]=useState(JSON.stringify([{
    statement:"Describe one independently justified behavior", expected_behavior:"Describe the expected result",
    input_domain:"Describe the supported finite JSON input domain", assumptions:[], ambiguities:[],
    provenance:{origin:"owner_authored_property",reference:"Owner specification",excerpt:"Replace with the specification fixed independently of the candidate",justification:"Explain why this expected behavior is justified",independent_of_candidate:true},
    approval:"unapproved",
  }],null,2));
  const [module,setModule]=useState(""),[exportName,setExport]=useState("");
  const [assertions,setAssertions]=useState('[{"id":"example","requirement_index":0,"args":[],"expected":null}]');
  const [setup,setSetup]=useState("[]"),[timeout,setTimeout]=useState(30);
  const [plan,setPlan]=useState<{id:string;plan:unknown;requirements:unknown[]}|null>(null);
  const [validation,setValidation]=useState<{id:string;status:string;evidence:unknown}|null>(null);
  const [approveRequirements,setApproveRequirements]=useState(false),[approveControls,setApproveControls]=useState(false),[approveExecution,setApproveExecution]=useState(false);
  const [busy,setBusy]=useState(false),[error,setError]=useState(""); const epoch=useRef(0);
  useEffect(()=>()=>{epoch.current++;},[]);
  function invalidate(){epoch.current++;setPlan(null);setValidation(null);setApproveControls(false);setApproveExecution(false);setError("");p.onChange(null);}
  async function prepare(){invalidate();const token=epoch.current;setBusy(true);p.onBusy(true);try {
    const input=JSON.parse(requirements);if(!Array.isArray(input)||!input.length||input.length>32)throw Error("Provide 1–32 requirements.");
    const records:{id:string}[]=[];
    for(const r of input){const source=r.provenance;if(!source?.excerpt)throw Error("Every requirement needs a source excerpt.");records.push(await api<{id:string}>("/repository-audits/requirements",{method:"POST",body:JSON.stringify({...r,version:"behavioral-requirement-v1",snapshot_id:p.snapshotId,approval:approveRequirements?"owner_approved":"unapproved",provenance:{...source,excerpt_hash:await hex(source.excerpt)}})}));}
    const checks=JSON.parse(assertions).map((c:{requirement_index:number;[key:string]:unknown})=>{const {requirement_index,...rest}=c;const req=records[requirement_index];if(!req)throw Error("Assertion references an unknown requirement index.");return {...rest,requirement_id:req.id};});
    const created=await api<{id:string;plan:unknown;requirements:unknown[]}>("/repository-audits/verification-plans",{method:"POST",body:JSON.stringify({snapshot_id:p.snapshotId,candidate_id:p.candidateId,candidate_hash:p.candidateHash,ordinary_plan_id:p.ordinaryPlanId,runtime:p.runtime,image_id:p.imageId,module,export:exportName,assertions:checks,setup:JSON.parse(setup),timeout_seconds:timeout})});
    if(token===epoch.current)setPlan(created);
  }catch(e){if(token===epoch.current)setError(String(e));}finally{if(token===epoch.current){setBusy(false);p.onBusy(false);}}}
  async function validate(){if(!plan||!approveControls)return;setApproveExecution(false);p.onChange(null);setValidation(null);const token=epoch.current;setBusy(true);p.onBusy(true);setError("");try {
    let run=await api<{id:string;status:string;evidence:unknown}>("/repository-audits/runs",{method:"POST",body:JSON.stringify({candidate_id:p.candidateId,plan_id:p.ordinaryPlanId,verification_id:plan.id,stage:"validation",approve_independent_plan:true,approve_exact_plan:true,confirm_local_execution:true})});
    while(token===epoch.current){setValidation(run);if(run.status!=="running")break;await new Promise(r=>window.setTimeout(r,700));if(token!==epoch.current)return;const next=await api<typeof run>(`/repository-audits/runs/${run.id}`);if(next.id!==run.id)throw Error("Validation identity mismatch");run=next;}
  }catch(e){if(token===epoch.current)setError(String(e));}finally{if(token===epoch.current){setBusy(false);p.onBusy(false);}}}
  const disabled=p.disabled||busy;
  return <section className="evaluation-panel" aria-label="Independent verification plan">
    <h2>4. Specify independent behavioral checks</h2>
    <p>Supply requirements justified separately from this patch. The checker supports finite JSON arguments and exact JSON results from a public Python or Node function. Expected values remain in the trusted broker. This establishes only the named examples.</p>
    <label>Independent requirements (JSON)<textarea aria-label="Independent requirements" rows={12} value={requirements} disabled={disabled} onChange={e=>{invalidate();setRequirements(e.target.value);setApproveRequirements(false);}}/></label>
    <label><input type="checkbox" checked={approveRequirements} disabled={disabled} onChange={e=>{invalidate();setApproveRequirements(e.target.checked);}}/>I reviewed the provenance, input domains, assumptions and expected behavior independently of the candidate. I approve these requirements.</label>
    <p>Ambiguous requirements and model hypotheses cannot authorize scoring. Model suggestions need separately supported, approved requirements. No model is called.</p>
    <label>Independent target file<input aria-label="Independent target file" value={module} disabled={disabled} onChange={e=>{invalidate();setModule(e.target.value);}}/></label>
    <label>Public function export<input aria-label="Public function export" value={exportName} placeholder="Leave empty for a Node module exporting a function" disabled={disabled} onChange={e=>{invalidate();setExport(e.target.value);}}/></label>
    <label>Named assertions (JSON)<textarea aria-label="Named assertions" rows={7} value={assertions} disabled={disabled} onChange={e=>{invalidate();setAssertions(e.target.value);}}/></label>
    <p>Each assertion includes <code>id</code>, zero-based <code>requirement_index</code>, <code>args</code>, optional Python <code>kwargs</code>, and <code>expected</code>. At least one assertion is required.</p>
    <label>Independent offline setup (JSON)<textarea aria-label="Independent offline setup" value={setup} disabled={disabled} onChange={e=>{invalidate();setSetup(e.target.value);}}/></label>
    <label>Independent timeout (seconds)<input aria-label="Independent timeout" type="number" min={1} max={120} value={timeout} disabled={disabled} onChange={e=>{invalidate();setTimeout(Number(e.target.value));}}/></label>
    <button disabled={disabled||!approveRequirements||!module} onClick={prepare}>Prepare independent plan</button>
    {error&&<p role="alert">{error}</p>}
    {plan&&<><details open><summary>Exact independent plan and requirement provenance</summary><pre>{JSON.stringify(plan,null,2)}</pre></details>
      <label><input type="checkbox" checked={approveControls} disabled={disabled} onChange={e=>setApproveControls(e.target.checked)}/>I approve running this plan's positive and negative synthetic controls in fresh restricted containers.</label>
      <button disabled={disabled||!approveControls} onClick={validate}>Validate independent checker</button></>}
    {validation&&<section aria-label="Independent validation result"><strong role="status">Checker validation: {words(validation.status)}</strong><p>Controls validate the adapter and named assertions. They do not establish that the selected target can load or that the specification is correct.</p><a href={`/api/repository-audits/runs/${validation.id}/evidence`} download>Download validation evidence</a>{validation.status==="running"&&<button onClick={()=>api(`/repository-audits/runs/${validation.id}/cancel`,{method:"POST"}).catch(e=>setError(String(e)))}>Cancel checker validation</button>}<details><summary>Inspect validation evidence</summary><pre>{JSON.stringify(validation.evidence,null,2)}</pre></details></section>}
    {plan&&validation?.status==="validation_passed"&&<label><input type="checkbox" aria-label="Approve validated independent plan" checked={approveExecution} disabled={disabled} onChange={e=>{setApproveExecution(e.target.checked);p.onChange(e.target.checked?{verification_id:plan.id,validation_run_id:validation.id,approve_independent_plan:true}:null);}}/>I inspected the exact requirements, verifier inputs, limits and successful controls. I approve this independent plan for this candidate.</label>}
  </section>;
}
