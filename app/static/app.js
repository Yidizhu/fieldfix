"use strict";
const i18n = window.FieldFixI18n;
let locale = i18n.detect();
let displayZone = i18n.read("fieldfix:time-zone") === "local" ? "local" : "UTC";
let appData = null, selected = null, busy = false, serviceOnline = false;
let researchData = {status:"unconfigured",datasets:[]};
let inferenceData = {status:"unconfigured"};
let initialSelectionResolved = false, checkoutNotice = null;
const drafts = new Map();
const disclosureStates = new Map();
let viewSignature = "";
const $ = id => document.getElementById(id);
const t = (key, params) => i18n.text(locale, key, params);
const colors = ["#3265c7", "#159581", "#ae7b36", "#9166b5"];
const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
const timeZone = () => displayZone === "local" ? browserZone : "UTC";
const number = value => new Intl.NumberFormat(locale).format(value);
const money = (amount, currency) => new Intl.NumberFormat(locale, {style:"currency", currency, currencyDisplay:"code"}).format(Number(amount)).replace(/\u00a0|\u202f/g, " ");
const dateTime = value => new Intl.DateTimeFormat(locale, {year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",timeZone:timeZone(),timeZoneName:"short"}).format(new Date(value));
function el(tag, cls, text) {const e = document.createElement(tag);if (cls) e.className = cls;if (text !== undefined) e.textContent = text;return e;}
function add(parent, ...children) {children.forEach(c => parent.append(c));return parent;}
function button(text, cls, action, disabled = false, id = "") {const b = el("button",cls,text);b.type="button";b.disabled=disabled||busy;if(id)b.id=id;b.addEventListener("click",action);return b;}
function toast(message, error = false) {const e=$("toast");e.textContent=message;e.className="toast"+(error?" error":"");e.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>e.hidden=true,6500);}
function applyStatic() {
  document.documentElement.lang=locale;document.documentElement.dir="ltr";document.title=t("title");
  document.querySelectorAll("[data-i18n]").forEach(e=>e.textContent=t(e.dataset.i18n));
  document.querySelectorAll("[data-i18n-aria]").forEach(e=>e.setAttribute("aria-label",t(e.dataset.i18nAria)));
  $("language").value=locale;$("timezone").value=displayZone;
  $("timezone").querySelector('[value="local"]').textContent=t("local_zone",{zone:browserZone});
}
function captureDraft() {
  if (!selected || !$("decision")) return;
  const draft=drafts.get(selected)||{};
  for(const id of ["decision","review-note","review-confirm","purchase-confirm","verify-note","verify-confirm","recovery-scenario","charge-confirm","void-confirm"]){
    const input=$(id);if(input)draft[id]=input.type==="checkbox"?input.checked:input.value;
  }
  drafts.set(selected,draft);
}
function restoreDraft() {
  const draft=drafts.get(selected);if(!draft)return;
  for(const [id,value] of Object.entries(draft)){
    const input=$(id);if(!input||input.disabled)continue;
    if(input.type==="checkbox") input.checked=value;else if(input.tagName!=="SELECT"||Array.from(input.options).some(o=>o.value===value)) input.value=value;
  }
}
function lockControls() {
  for(const id of ["language","timezone","filter","refresh","nav-cases","nav-settings","nav-status","nav-research"])$(id).disabled=busy;
  document.querySelectorAll("[data-view]").forEach(e=>e.disabled=busy);
  if(busy)document.querySelectorAll("#detail button,#detail input,#detail select,#detail textarea,#case-list button").forEach(e=>e.disabled=true);
}
async function fetchCases(language) {
  let response;try{response=await fetch(`/api/cases?lang=${encodeURIComponent(language)}`);}catch(_){throw Error(t("load_failed"));}
  if(!response.ok)throw Error(t("load_failed"));
  return response.json();
}
// Checkout parameters are navigation hints only. Workflow state comes from the server.
function resolveInitialSelection(data) {
  if(initialSelectionResolved)return;
  initialSelectionResolved=true;
  const url=new URL(window.location.href),caseId=url.searchParams.get("case");
  selected=data.cases.some(c=>c.id===caseId)?caseId:data.cases[0]?.id;
  const checkout=url.searchParams.get("checkout"),token=url.searchParams.get("token");
  if(!["return","cancel"].includes(checkout)||token===null)return;
  const matches=token?data.cases.filter(c=>c.workflow.payment?.order_id===token):[];
  if(matches.length!==1){checkoutNotice={key:"checkout_unknown"};return;}
  selected=matches[0].id;
  checkoutNotice={key:checkout==="cancel"?"checkout_canceled":"checkout_returned",caseId:selected};
  url.searchParams.set("case",selected);
  url.searchParams.delete("token");url.searchParams.delete("PayerID");
  window.history.replaceState(window.history.state,"",url.pathname+url.search+url.hash);
}
function sandboxEvidenceLevel() {
  if(!appData.sandbox_configured)return "unconfigured";
  const payments=appData.cases.map(c=>c.workflow.payment).filter(p=>p?.mode==="paypal_sandbox");
  if(payments.some(p=>p.status==="completed"&&p.capture_id))return "charged";
  if(payments.some(p=>p.status==="authorized"&&p.authorization_id))return "authorized";
  return "configured";
}
async function load(language = locale) {
  if(busy)return false;
  captureDraft();busy=true;lockControls();
  try {
    const [data,research,inference]=await Promise.all([fetchCases(language),
      fetch(`/api/research?lang=${encodeURIComponent(language)}`).then(r=>{if(!r.ok)throw Error();return r.json();}).catch(()=>({status:"invalid",datasets:[]})),
      fetch(`/api/research-inference?lang=${encodeURIComponent(language)}`).then(r=>{if(!r.ok)throw Error();return r.json();}).catch(()=>({status:"invalid"}))]);
    researchData=research;inferenceData=inference;
    appData=data;serviceOnline=true;locale=language;resolveInitialSelection(data);
    i18n.write("fieldfix:locale",locale);applyStatic();$("toast").hidden=true;
    return true;
  } catch(error) {serviceOnline=false;$("language").value=locale;toast(error.message,true);$("connection").textContent=t("offline");$("service-status").textContent=t("offline");return false;}
  finally {busy=false;lockControls();render();}
}
async function act(action, body = {}) {
  if(busy)return;captureDraft();const caseId=selected;busy=true;lockControls();
  try {
    let response;try{response=await fetch(`/api/cases/${encodeURIComponent(caseId)}/${action}?lang=${encodeURIComponent(locale)}`,{method:"POST",headers:{"Content-Type":"application/json","X-FieldFix-Token":appData.csrf},body:JSON.stringify(body)});}catch(_){throw Error(t("operation_failed"));}
    const result=await response.json();if(!response.ok)throw Error(result.error||t("operation_failed"));
    appData=await fetchCases(locale);serviceOnline=true;
    // A successful save is authoritative; failed submissions retain their draft.
    const draft=drafts.get(caseId)||{};
    const clear=action==="review"?["decision","review-note","review-confirm","purchase-confirm","verify-note","verify-confirm"]:action==="approve"?["purchase-confirm"]:action==="verify_repair"?["verify-note","verify-confirm"]:action==="submit_recovery"?["verify-note","verify-confirm","charge-confirm"]:action==="capture"?["charge-confirm"]:action==="void"?["void-confirm","charge-confirm"]:[];
    clear.forEach(key=>delete draft[key]);drafts.set(caseId,draft);
    toast(t(action==="rehearse"?"rehearsed_toast":"saved"));
  } catch(error) {
    // An uncertain network operation can persist a reconciliation lock.
    try {appData=await fetchCases(locale);} catch(_) {serviceOnline=false;}
    toast(error.message,true);
  }
  finally {busy=false;lockControls();render();}
}
function needsAiReview(c) {
  const w=c.workflow;
  return !!(c.ai&&w.review&&!w.payment&&(!w.ai_review||w.ai_review.evidence_sha256!==c.ai.evidence_sha256||c.ai.status!=="ready"));
}
function needsCaseReview(c) {return c.analysis.category!=="normal"&&(!c.workflow.review||needsAiReview(c));}
function render() {
  if(!appData)return;
  $("session-mode").hidden=appData.session_mode!=="offline_demo";
  $("session-mode").textContent=t("offline_demo_help");
  const sandboxLevel=sandboxEvidenceLevel();
  $("service-status").textContent=t(serviceOnline?"service_ready":"offline");
  $("connection").textContent=t(serviceOnline?"online_"+sandboxLevel:"offline");
  $("count-total").textContent=number(appData.cases.length);
  $("count-review").textContent=number(appData.cases.filter(needsCaseReview).length);
  $("count-done").textContent=number(appData.cases.filter(c=>c.workflow.review).length);
  $("sandbox-tag").textContent=t(["authorized","charged"].includes(sandboxLevel)?"sandbox_"+sandboxLevel+"_tag":sandboxLevel);
  $("sandbox-description").textContent=t("sandbox_"+sandboxLevel);
  if(appData.session_mode==="offline_demo"){
    $("sandbox-tag").textContent=t("offline_demo");
    $("sandbox-description").textContent=t("offline_demo_help");
  }
  renderQueue();renderDetail();lockControls();
  window.FieldFixResearch.render($("research-content"),researchData,locale,inferenceData);
}
function label(category){return ["shared_connection","reading_anomaly","normal","insufficient_data"].includes(category)?t(category):category;}
function progressLabel(c) {
  return t("progress_"+window.FieldFixFlowView.progress(c.workflow,{needsReview:needsAiReview(c),normal:c.analysis.category==="normal"}));
}
function renderQueue() {
  const list=$("case-list");list.replaceChildren();const filter=$("filter").value;
  const cases=appData.cases.filter(c=>filter==="all"||(filter==="normal"?c.analysis.category==="normal":needsCaseReview(c)));
  if(!cases.some(c=>c.id===selected))selected=cases[0]?.id||null;
  for(const c of cases){
    const b=button("","case-button"+(selected===c.id?" selected":""),()=>{captureDraft();selected=c.id;render();});
    b.setAttribute("aria-pressed",String(selected===c.id));
    add(b,add(el("div","case-top"),el("span","",c.id),el("span","pill",progressLabel(c))),el("strong","",c.title),el("small","",c.site));list.append(b);
  }
  if(!cases.length)list.append(el("div","empty",t("empty_filter")));
}
function disclosure(id,title,open=false,cls="evidence-details"){
  const key=selected+":"+viewSignature+":"+id,details=el("details",cls);
  details.id=id;details.open=disclosureStates.has(key)?disclosureStates.get(key):open;
  details.append(el("summary","",title));
  details.addEventListener("toggle",()=>{if(details.isConnected)disclosureStates.set(key,details.open);});
  return details;
}
function step(n,title){
  const details=disclosure("step-"+n,title,false,"action-step");
  details.dataset.step=n;
  return details;
}
function check(text,id){const wrap=el("label","check"),input=el("input");input.type="checkbox";input.id=id;wrap.htmlFor=id;add(wrap,input,el("span","",text));return {wrap,input};}
function fieldLabel(text,id){const label=el("label","field-label",text);label.htmlFor=id;return label;}
function aiReason(c) {
  const ai=c.ai;if(!ai)return null;
  const desired=ai.summary_code==="persistent_shift"?"median_residual_vwc":ai.summary_code==="stuck"?"flat_duration_hours":"trailing_missing_hours";
  const signal=ai.signals?.find(s=>s.code===desired),device=c.series.find(d=>d.id===signal?.device_id);
  const value=typeof signal?.value==="number"?new Intl.NumberFormat(locale,{maximumFractionDigits:2,signDisplay:signal.code==="median_residual_vwc"?"exceptZero":"auto"}).format(signal.value):"—";
  const code=ai.summary_code;
  if(code==="shared_dropout")return t("ai_shared_reason",{count:ai.devices.filter(d=>d.pattern==="dropout").length});
  if(code==="persistent_shift"||code==="stuck")return t(code==="stuck"?"ai_stuck_reason":"ai_shift_reason",{device:device?.name||signal?.device_id||"—",value});
  return t("ai_"+({single_dropout:"gap",normal:"normal",insufficient:"insufficient",unavailable:"unavailable",disagreement:"disagreement"}[code]||"insufficient")+"_reason");
}
function appendAiEvidence(parent,c) {
  const ai=c.ai;if(!ai)return;
  add(parent,el("h3","",t("ai_evidence")));
  for(const signal of ai.signals||[]) {
    const device=c.series.find(d=>d.id===signal.device_id),value=typeof signal.value==="number"?new Intl.NumberFormat(locale,{maximumFractionDigits:3}).format(signal.value):"—";
    parent.append(el("p","",`${device?.name||signal.device_id} · ${t("ai_signal_"+signal.code)}: ${value} ${t("ai_unit_"+signal.unit)}`));
    if(signal.source_range?.start&&signal.source_range?.end)parent.append(el("p","method",t("ai_source_range",{start:dateTime(signal.source_range.start),end:dateTime(signal.source_range.end)})));
  }
}
function renderDetail() {
  const c=appData.cases.find(c=>c.id===selected),detail=$("detail");detail.replaceChildren();
  if(!c){detail.append(el("div","empty",t("empty_filter")));return;}
  if(checkoutNotice&&(!checkoutNotice.caseId||checkoutNotice.caseId===c.id)){
    const notice=el("p","warning",t(checkoutNotice.key,{case:checkoutNotice.caseId}));
    notice.id="checkout-notice";notice.setAttribute("role","status");detail.append(notice);
  }
  const a=c.analysis,w=c.workflow;
  const pending=w.pending_operation;
  const pendingAction=typeof pending==="string"?pending:(pending?.action||pending?.operation||pending?.type||"");
  const legacy=!!(w.legacy||w.legacy_payment||(w.payment&&w.payment.intent!=="AUTHORIZE"));
  const blocked=action=>!!pending&&pendingAction!==action;
  const aiNeedsReview=needsAiReview(c);
  const focus=window.FieldFixFlowView.focus(aiNeedsReview?{...w,review:null,approved:false,quote:null}:w);
  viewSignature=JSON.stringify([focus.stages,pendingAction,w.payment?.status,w.recovery?.status,w.repair,!!w.approved,!!w.review]);
  detail.append(add(el("div","detail-head"),add(el("div"),el("span","pill",progressLabel(c)),el("h2","",c.title),el("p","",c.site)),button(t("case_report"),"secondary",()=>downloadReport(c),false,"download-report")));
  const body=el("div","case-body"),evidence=el("div","evidence-pane"),actions=el("aside","action-pane");
  const category=["shared_connection","reading_anomaly","normal","insufficient_data"].includes(a.category)?a.category:"insufficient_data";
  const overview=el("section","case-overview");overview.id="case-overview";
  const nextReason=focus.reason==="review"?category:focus.reason==="payment"&&w.payment?.status==="awaiting_buyer"?"awaiting_buyer":focus.reason;
  const whyReason=["completed","voided","reviewed"].includes(nextReason)?"recorded":nextReason;
  add(overview,el("h3","",t("what_happened")),el("p","",a.summary),el("h3","",t("suggested_action")),el("p","recommended-action",t("next_"+nextReason)));
  if(!["completed","voided","reviewed"].includes(focus.reason))add(overview,el("h3","",t("why_this_action")),el("p","",focus.reason==="review"&&c.ai?aiReason(c):t("why_"+whyReason)));
  if(c.ai?.status!=="ready"&&c.ai)overview.append(el("p","warning",t("ai_unready")));
  if(aiNeedsReview)overview.append(el("p","warning",t("ai_changed")));
  evidence.append(overview);
  const observations=disclosure("observation-details",t("view_evidence"));
  observations.append(add(el("div","section-label"),el("h3","",t("moisture")),el("span","",t("chart_label"))));
  const canvas=el("canvas");canvas.setAttribute("role","img");canvas.setAttribute("aria-label",t("chart_accessible"));observations.append(add(el("div","chart-wrap"),canvas));
  observations.addEventListener("toggle",()=>{if(observations.open)requestAnimationFrame(()=>draw(canvas,c.series));});
  const legend=el("div","legend");c.series.forEach((s,index)=>{const dot=el("i");dot.style.backgroundColor=colors[index%colors.length];legend.append(add(el("span"),dot,document.createTextNode(s.name||s.id)));});observations.append(legend);
  const points=c.series[0]?.points||[];
  if(points.length)observations.append(el("p","chart-range",t("chart_range",{start:dateTime(points[0].t),end:dateTime(points[points.length-1].t)})));
  observations.append(el("p","chart-range",c.gateway_id||t("gateway_unknown")));
  const list=el("ul","evidence-list");a.evidence.forEach(text=>list.append(el("li","",text)));
  const next=el("ul","evidence-list");a.next_steps.forEach(text=>next.append(el("li","",text)));
  appendAiEvidence(observations,c);
  add(observations,el("h3","",t(c.ai?"baseline_checks":"evidence")),list,el("h3","",t("next_checks")),next);
  const sources=disclosure("analysis-sources",t("analysis_sources"));
  add(sources,el("p","",a.method));
  if(c.ai){
    sources.append(el("p","",t("ai_scope")));
    if(c.ai.model?.id)sources.append(el("p","source-fingerprint",t("ai_model_source",{model:c.ai.model.id,hash:c.ai.model.sha256||"—"})));
    if(w.ai_review)sources.append(el("p","",t(w.ai_review.evidence_sha256===c.ai.evidence_sha256?"ai_reviewed":"ai_existing")));
    else if(w.payment)sources.append(el("p","",t("ai_legacy")));
  }
  sources.append(button(t("export"),"secondary",()=>download(c),false,"export-evidence"));
  observations.append(sources);
  evidence.append(observations);
  actions.append(el("h3","action-heading",t(["completed","voided","reviewed"].includes(focus.reason)?"recorded_result":"current_step")));

  const review=step("1",t("review"));review.append(el("p","",t(w.review?(w.payment?"review_locked":"review_editable"):"review_help")));
  const select=el("select","form-select");select.id="decision";select.setAttribute("aria-label",t("decision"));
  ["inspect_connection","observe","replace","warranty"].forEach(value=>{if(["replace","warranty"].includes(value)&&a.category!=="reading_anomaly")return;const option=el("option","",t(value));option.value=value;select.append(option);});
  select.value=w.review?.decision||(a.category==="shared_connection"?"inspect_connection":"observe");
  const note=el("textarea");note.id="review-note";note.dir="auto";note.maxLength=1000;note.placeholder=t("review_placeholder");note.setAttribute("aria-label",t("review_note"));note.value=w.review?.note||"";
  const confirm=check(t("review_confirm"),"review-confirm");
  if(w.payment||pending||legacy){select.disabled=true;note.disabled=true;confirm.input.disabled=true;confirm.input.checked=true;}
  add(review,fieldLabel(t("decision"),"decision"),select,fieldLabel(t("inspection_label"),"review-note"),note,confirm.wrap,button(t("save_review"),"primary",()=>act("review",{decision:select.value,note:note.value,confirmed:confirm.input.checked}),!!w.payment||!!pending||legacy,"save-review"));actions.append(review);

  const purchase=step("2",t("procurement"));
  if(w.review?.decision==="warranty")purchase.append(el("p","",t("warranty_help")));
  else if(w.review?.decision==="replace"){
    const amount=money(w.quote?.amount||"25.00",w.quote?.currency||"NZD");
    purchase.append(el("p","",t("service_roles")));
    purchase.append(add(el("div","product"),el("span","price",amount),el("strong","",w.quote?.sku||"FF-Soil-01"),el("small","",t("demo_catalog"))));
    if(w.approved)purchase.append(el("p","approved-note",t(w.repair==="verified_demo"?"procurement_followup":"procurement_approved")));
    else {const approval=check(t("approve_confirm",{amount}),"purchase-confirm");add(purchase,approval.wrap,button(t("approve"),"primary",()=>act("approve",{confirmed:approval.input.checked}),!!pending||legacy||aiNeedsReview,"approve-procurement"));}
  } else purchase.append(el("p","",t(a.category==="shared_connection"?"shared_no_buy":"no_buy")));
  actions.append(purchase);

  const payment=step("3",t("payment_followup")),pay=w.payment;
  if(legacy){
    add(payment,el("h3","",t("legacy_payment")),el("p","warning",t("legacy_explanation")));
    if(pay)payment.append(el("p","transaction-id",pay.capture_id||pay.authorization_id||pay.order_id||pay.record_id||""));
  }else{
    if(pending){
      const actionName={create_order:t("create_order"),authorize:t("authorize"),capture:t("capture"),void:t("void_action")}[pendingAction]||t("reconcile");
      payment.append(el("p","warning",t("pending_operation",{action:actionName})));
      if(pay?.mode==="paypal_sandbox"&&pay.order_id)payment.append(button(t("reconcile"),"secondary",()=>act("reconcile"),false,"reconcile-payment"));
    }
    if(pay){
      const statusKey="payment_"+pay.status;
      const known=["awaiting_buyer","authorized","completed","voided","pending","expired","denied"].includes(pay.status);
      const state=t(known?statusKey:"payment_unknown");
      payment.append(el("p",pay.mode==="local_rehearsal"||!["authorized","completed","voided"].includes(pay.status)?"warning":"approved-note",t(pay.mode==="local_rehearsal"?"local_payment":"sandbox_payment",{state})));
      payment.append(el("p","transaction-id",pay.capture_id||pay.authorization_id||pay.order_id||pay.record_id||""));
      if(pay.expires_at&&!Number.isNaN(Date.parse(pay.expires_at)))payment.append(el("p","",t("authorization_expires",{time:dateTime(pay.expires_at)})));
      if(pay.status==="awaiting_buyer"||pendingAction==="authorize"){
        if(pay.approval_url&&pay.status==="awaiting_buyer"&&(!pending||pendingAction==="authorize")){
          const link=el("a","secondary",t("buyer_link"));link.href=pay.approval_url;link.target="_blank";link.rel="noopener noreferrer";payment.append(link);
        }
        payment.append(button(t("authorize"),"secondary",()=>act("authorize"),blocked("authorize"),"authorize-order"));
      }
      if(pay.status==="authorized")payment.append(el("p","",t("hold_explanation")));
      if(pay.capture_before&&!Number.isNaN(Date.parse(pay.capture_before)))payment.append(el("p","warning",t("capture_deadline",{time:dateTime(pay.capture_before)})));
    }else if(w.approved){
      if(w.quote)payment.append(add(el("div","product"),el("span","price",money(w.quote.amount,w.quote.currency)),el("strong","",w.quote.sku),el("small","",t("approved_quote"))));
      const localOnly=appData.session_mode==="offline_demo"||!appData.sandbox_configured;
      payment.append(el("p","",t(localOnly?"demo_payment_note":"sandbox_funds")));
      if(localOnly)payment.append(button(t("rehearse"),"primary",()=>act("rehearse"),!!pending||aiNeedsReview,"rehearse-payment"));
      else payment.append(button(t("create_order"),"primary",()=>act("create_order"),blocked("create_order")||aiNeedsReview,"create-order"));
    }else payment.append(el("p","",t("payment_gated")));
  }
  actions.append(payment);

  const recovery=step("4",t("recovery_title")),r=w.recovery;
  if(!legacy&&w.review&&w.review.decision!=="warranty"){
    recovery.append(el("p","",t("recovery_help")));
    const scenario=el("select","form-select");scenario.id="recovery-scenario";
    for(const value of ["recovered","still_faulty","insufficient"]){const o=el("option","",t(value));o.value=value;scenario.append(o);}
    scenario.value=r?.scenario||"recovered";
    const canSubmit=(w.review.decision!=="replace"||pay?.status==="authorized")&&!pending;
    scenario.disabled=!canSubmit;
    add(recovery,fieldLabel(t("recovery_scenario"),"recovery-scenario"),scenario,
      button(t("submit_recovery"),"secondary",()=>act("submit_recovery",{scenario:scenario.value}),!canSubmit,"submit-recovery"));
    if(w.review.decision==="replace"&&(!pay||pay.status!=="authorized"))recovery.append(el("p","",t(pay&&["completed","voided"].includes(pay.status)?"recovery_locked":"recovery_gated")));
    if(!r)recovery.append(el("p","warning",t("recovery_none")));
    else {
      recovery.append(el("p",r.status==="pass"?"approved-note":"warning",t("recovery_"+(r.status==="pass"?"pass":r.status==="fail"?"fail":"insufficient"))));
    }
  }
  if(r){
    evidence.append(el("p",r.status==="pass"?"recovery-state":"warning",t("recovery_"+(r.status==="pass"?"pass":r.status==="fail"?"fail":"insufficient"))));
    const results=disclosure("recovery-evidence",t("view_recovery"));
    add(results,el("h3","",t("recovery_title")),el("p","",t("recovery_samples",{count:number(r.sample_count||0)})),el("p","",t("recovery_boundary")));
    if(r.display_explanation||r.explanation)results.append(el("p","",r.display_explanation||r.explanation));
    const checks=el("ul","evidence-list");
    const knownChecks=["observation_window","paired_samples","link_samples","link_success_ratio","reference_variation","mean_absolute_error","max_absolute_error","sensor_variation"];
    const format=value=>typeof value==="boolean"?t(value?"check_yes":"check_no"):typeof value==="number"&&Number.isFinite(value)?new Intl.NumberFormat(locale,{maximumFractionDigits:r.metrics?.metric_decimal_places||4}).format(value):t("not_available");
    for(const item of r.checks||[]){
      if(item.code==="observation_window"){checks.append(el("li","",t("window_check_line",{label:t(item.code),status:t("check_"+item.status),detail:t(item.value?"window_valid":"window_invalid")})));continue;}
      const unitKey={count:"unit_count",samples:"unit_count",hours:"unit_hours",ratio:"unit_ratio",percentage_points:"unit_pp",percentage_point:"unit_pp",pp:"unit_pp",hourly_window:"unit_window"}[item.unit];
      const unit=unitKey?t(unitKey):item.unit||"";
      checks.append(el("li","",t("check_line",{label:knownChecks.includes(item.code)?t(item.code):item.code,status:t("check_"+(["pass","fail"].includes(item.status)?item.status:"insufficient")),value:format(item.value),operator:({eq:"=",gte:"≥",lte:"≤",gt:">",lt:"<"}[item.operator]||item.operator||""),threshold:format(item.threshold),unit})));
    }
    add(results,el("h3","",t("recovery_checks")),checks);evidence.append(results);
    if(Array.isArray(r.observations)&&r.observations.length){
      const after=el("canvas");after.setAttribute("role","img");after.setAttribute("aria-label",t("recovery_chart"));
      const series=[{name:t("recovery_sensor"),points:r.observations.map(x=>({t:x.t,value:x.sensor}))},{name:t("recovery_reference"),points:r.observations.map(x=>({t:x.t,value:x.reference}))}];
      add(results,el("p","",t("recovery_chart")),add(el("div","chart-wrap"),after));
      const key=el("div","legend");series.forEach((item,i)=>{const dot=el("i");dot.style.backgroundColor=colors[i];key.append(add(el("span"),dot,document.createTextNode(item.name)));});results.append(key);
      requestAnimationFrame(()=>{if(after.isConnected&&!$("workspace").hidden)draw(after,series);});
      results.addEventListener("toggle",()=>{if(results.open)requestAnimationFrame(()=>draw(after,series));});
    }
  }
  const nonCharge=w.review&&!["replace","warranty"].includes(w.review.decision);
  if(!legacy&&nonCharge)recovery.append(el("p","",t("noncharge_followup")));
  recovery.append(el("p","",t("acceptance_role")));
  const canVerify=!legacy&&!pending&&r?.status==="pass"&&(nonCharge||pay?.status==="authorized");
  if(w.repair==="verified_demo")recovery.append(el("p","approved-note",t("followup_done")));
  else if(canVerify){
    const verifyNote=el("textarea");verifyNote.id="verify-note";verifyNote.dir="auto";verifyNote.placeholder=t("followup_placeholder");verifyNote.maxLength=1000;verifyNote.setAttribute("aria-label",t("followup_note"));
    const verify=check(t("followup_confirm"),"verify-confirm");
    add(recovery,fieldLabel(t("followup_label"),"verify-note"),verifyNote,verify.wrap,button(t("save_followup"),"secondary",()=>act("verify_repair",{note:verifyNote.value,confirmed:verify.input.checked}),false,"save-followup"));
  }else if(!legacy&&w.review&&w.review.decision!=="warranty")recovery.append(el("p","warning",t("recovery_review_blocked")));
  if(w.review||r)actions.append(recovery);

  if(pay&&!legacy){
    const charge=step("5",t("charge_title"));
    if(["completed","voided"].includes(pay.status))charge.append(el("p","approved-note",t(pay.mode==="local_rehearsal"?"local_payment":"sandbox_payment",{state:t("payment_"+pay.status)})));
    else charge.append(el("p","",t("charge_help")));
    if(pay.status==="authorized"||pendingAction==="capture"){
      const canCharge=w.repair==="verified_demo"&&r?.status==="pass"&&!blocked("capture");
      const confirmCharge=check(t("charge_confirm",{amount:money(pay.amount||"25.00",pay.currency||"NZD")}),"charge-confirm");confirmCharge.input.disabled=!canCharge;
      add(charge,confirmCharge.wrap,button(t("capture"),"primary",()=>act("capture",{confirmed:confirmCharge.input.checked}),!canCharge,"capture-order"));
      if(!canCharge)charge.append(el("p","warning",t("charge_blocked")));
    }
    if(pay.status==="authorized"||pendingAction==="void"){
      const confirmVoid=check(t("void_confirm"),"void-confirm");confirmVoid.input.disabled=blocked("void");
      add(charge,el("p","",t("void_help")),confirmVoid.wrap,button(t("void_action"),"secondary",()=>act("void",{confirmed:confirmVoid.input.checked}),blocked("void"),"void-authorization"));
    }
    actions.append(charge);
  }
  // State comes first, independent of collapsed controls. Do not imply that a
  // completed payment certifies recovery, or that a local rehearsal called PayPal.
  if(pay||pending||legacy){
    const status=el("section","case-status");status.id="case-status";
    status.append(el("h3","",t("current_status")));
    if(legacy)status.append(el("p","warning",t("legacy_explanation")));
    if(pending)status.append(el("p","warning",t("pending_short")));
    if(pay){
      const known=["awaiting_buyer","authorized","completed","voided","pending","expired","denied"].includes(pay.status);
      const safeState=t(known?"payment_"+pay.status:"payment_unknown");
      status.append(el("p",["completed","voided"].includes(pay.status)?"":"status-attention",t(pay.mode==="local_rehearsal"?"local_payment":"sandbox_payment",{state:safeState})));
      status.append(el("p","",money(pay.amount||w.quote?.amount||"25.00",pay.currency||"NZD")));
      if(pay.status==="authorized"){
        status.append(el("p","",t("hold_short")));
        if(pay.expires_at&&!Number.isNaN(Date.parse(pay.expires_at)))status.append(el("p","",t("authorization_expires",{time:dateTime(pay.expires_at)})));
        if(pay.capture_before&&!Number.isNaN(Date.parse(pay.capture_before)))status.append(el("p","warning",t("capture_deadline",{time:dateTime(pay.capture_before)})));
      }
      if(pay.status==="authorized"&&!(r?.status==="pass"&&w.repair==="verified_demo"))status.append(el("p","warning",t("charge_blocked")));
      if(w.repair==="verified_demo")status.append(el("p","",t("repair_recorded_short")));
      else status.append(el("p","",t("repair_unverified_short")));
    }
    evidence.insertBefore(status,observations);
  }
  for(const section of actions.querySelectorAll(".action-step")){
    const n=Number(section.dataset.step),key=selected+":"+viewSignature+":"+section.id;
    if(!disclosureStates.has(key))section.open=focus.stages.includes(n);
    section.classList.toggle("current",focus.stages.includes(n));
    if(focus.stages.includes(n))section.querySelector("summary").append(el("small","current-marker",t("step_now")));
  }
  if(pay?.status==="authorized"&&!legacy&&!blocked("void")&&!focus.stages.includes(5)){
    const exit=button(t("stop_without_charge"),"text-action",()=>{
      const target=$("step-5");target.open=true;target.scrollIntoView({block:"nearest"});$("void-confirm")?.focus();
    });
    actions.append(exit);
  }
  detail.append(add(body,evidence,actions));
  const log=disclosure("activity-log",t("history",{count:number(w.history.length)}),false,"log");
  log.append(el("p","source-language-note",t("notes_original",{zone:timeZone()})));
  const logs=el("ol","log-list");if(!w.history.length)logs.append(el("li","empty-log",t("empty_history")));
  for(const event of [...w.history].reverse()){const when=el("time","",dateTime(event.at));when.dateTime=event.at;const text=el("span","",event.display_text||event.text);text.dir="auto";logs.append(add(el("li"),when,text));}
  detail.append(add(log,logs));restoreDraft();requestAnimationFrame(()=>{if(canvas.isConnected&&!$("workspace").hidden)draw(canvas,c.series);});
}
function draw(canvas, series) {
  const rect=canvas.getBoundingClientRect(),dpr=devicePixelRatio||1;if(!rect.width)return;
  canvas.width=rect.width*dpr;canvas.height=rect.height*dpr;
  const ctx=canvas.getContext("2d");ctx.scale(dpr,dpr);const w=rect.width,h=rect.height,L=35,R=12,T=12,B=26;
  const values=series.flatMap(s=>s.points.map(p=>p.value)).filter(v=>typeof v==="number"&&Number.isFinite(v));if(!values.length)return;
  const min=Math.floor(Math.min(...values)-2),max=Math.ceil(Math.max(...values)+2),n=Math.max(...series.map(s=>s.points.length));
  ctx.font="10px Segoe UI";ctx.lineWidth=1;
  for(let index=0;index<5;index++){const y=T+(h-T-B)*index/4;ctx.strokeStyle="#e5ebf2";ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(w-R,y);ctx.stroke();ctx.fillStyle="#718398";ctx.fillText(number(Math.round(max-(max-min)*index/4)),3,y+3);}
  series.forEach((s,index)=>{ctx.strokeStyle=colors[index%colors.length];ctx.lineWidth=2;ctx.beginPath();let active=false;s.points.forEach((point,i)=>{if(typeof point.value!=="number"){active=false;return;}const x=L+(w-L-R)*i/Math.max(1,n-1),y=T+(h-T-B)*(max-point.value)/(max-min);if(active)ctx.lineTo(x,y);else ctx.moveTo(x,y);active=true;});ctx.stroke();});
  ctx.fillStyle="#718398";ctx.fillText(t("replay_start"),L,h-4);ctx.fillText(t("replay_end"),Math.max(L,w-R-ctx.measureText(t("replay_end")).width),h-4);
}
function download(c) {
  const blob=new Blob([JSON.stringify({exported_at:new Date().toISOString(),display_locale:locale,display_time_zone:timeZone(),disclosure:"Synthetic observations and simulated manual records. A classifier trained on synthetic sequences and independent rules provide inspection leads, not validated hardware diagnoses. Review-bound AI evidence and original notes are preserved; current AI does not retroactively justify an old transaction.",case:c},null,2)],{type:"application/json"});
  const url=URL.createObjectURL(blob),anchor=el("a");anchor.href=url;anchor.download=`FieldFix-${c.id}-evidence.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function downloadReport(c) {
  try {
    const response=await fetch(`/api/cases/${encodeURIComponent(c.id)}/report?lang=${encodeURIComponent(locale)}`);
    if(!response.ok || !response.headers.get("Content-Type")?.startsWith("text/html"))throw Error();
    const url=URL.createObjectURL(await response.blob()),anchor=el("a");
    anchor.href=url;anchor.download=`FieldFix-${c.id}-${locale}-report.html`;anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch(_) {toast(t("report_failed"),true);}
}
function showPanel(view){
  if(busy||!["cases","settings","status","research"].includes(view))return;
  captureDraft();
  window.scrollTo({top:0,behavior:"instant"});
  for(const [name,id] of [["cases","workspace"],["settings","settings-panel"],["status","status-panel"],["research","research-panel"]]){
    $(id).hidden=name!==view;
    const control=$("nav-"+name);
    control.classList.toggle("active",name===view||(name==="settings"&&view!=="cases"));
    if(name===view)control.setAttribute("aria-current","page");else control.removeAttribute("aria-current");
  }
  if(view==="cases")render();
  if(view==="research")window.FieldFixResearch.render($("research-content"),researchData,locale,inferenceData);
  const heading=document.querySelector("main>section:not([hidden]) h1");
  if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
}
$("language").addEventListener("change",()=>load($("language").value));
$("timezone").addEventListener("change",()=>{captureDraft();displayZone=$("timezone").value;i18n.write("fieldfix:time-zone",displayZone);render();});
$("filter").addEventListener("change",()=>{captureDraft();render();});
$("refresh").addEventListener("click",()=>load());
$("nav-cases").addEventListener("click",()=>showPanel("cases"));$("nav-status").addEventListener("click",()=>showPanel("status"));
$("nav-settings").addEventListener("click",()=>showPanel("settings"));
$("nav-research").addEventListener("click",()=>showPanel("research"));
document.querySelectorAll("[data-view]").forEach(e=>e.addEventListener("click",()=>showPanel(e.dataset.view)));
let timer;window.addEventListener("resize",()=>{clearTimeout(timer);timer=setTimeout(()=>{if(!$("workspace").hidden){const c=appData?.cases.find(c=>c.id===selected),canvas=$("detail").querySelector("canvas");if(c&&canvas)draw(canvas,c.series);}},200);});
applyStatic();load();
