"use strict";
// Read-only experiment results and separately verified local inference runs.
window.FieldFixResearch = (() => {
  const instances = new WeakMap();
  const DAY = 86400000;
  const rows = [
    ["kicker", "研究证据 · 只读回放", "Research evidence · Read-only replay"],
    ["title", "研究中看到了什么", "What the study shows"],
    ["intro", "对比未加入故障与人为加入故障的实验结果。", "Compare results with and without deliberately injected faults."],
    ["boundary", "按天回放的实验结果，非实时诊断；尚未验证真实硬件故障。", "Saved daily experiment results, not live diagnosis or verified hardware faults."],
    ["no_link", "此处仅查看研究证据，不会创建案件、批准换货或触发付款。", "This view only presents research evidence. It does not create a case, approve a replacement or trigger payment."],
    ["choose", "想看哪种情况？", "Which example would you like to see?"],
    ["unconfigured", "尚未配置研究结果回放。", "No research replay is configured."],
    ["unconfigured_help", "需要先由本机服务提供经过筛选的结果摘要；这里不会补入虚构示例。", "The local service must first provide an approved results summary. No example is fabricated here."],
    ["invalid", "研究结果暂时无法展示。", "Research results cannot be displayed."],
    ["invalid_help", "结果缺失、格式无效或不符合回放约定。请检查本机导入结果；本页不会猜测分数、阈值或报警。", "Results are missing, invalid or outside the replay contract. Check the local import. This view will not infer scores, thresholds or flags."],
    ["empty", "此回放中没有可展示的研究示例。", "This replay contains no research examples."],
    ["no_points", "此示例没有逐日结果。", "This example contains no daily results."],
    ["no_valid", "此窗口没有有效分数；数据缺失不等于正常。", "This window has no valid scores. Missing data does not mean normal operation."],
    ["research_output_with_injected_faults", "研究输出 · 含注入故障实验", "Research output · Injected-fault experiment"],
    ["synthetic_contract_fixture", "合成接口测试示例 · 非研究结果", "Synthetic contract fixture · Not research results"],
    ["model", "模型 / 原始算法名", "Model / Original algorithm name"],
    ["score_name", "分数 / 原始指标名", "Score / Original metric name"],
    ["scenario", "实验场景代码", "Scenario code"],
    ["window", "源数据日期窗口", "Source date window"],
    ["points", "记录点数", "Recorded points"],
    ["valid_points", "有效分数点", "Valid score points"],
    ["missing_points", "缺失点数", "Missing points"],
    ["alarm_points", "越过阈值的天数（重算）", "Days above threshold (recomputed)"],
    ["alarm_fraction", "越过阈值的比例（重算）", "Share of days above threshold (recomputed)"],
    ["chart_title", "哪些天值得留意？", "Which days deserve a closer look?"],
    ["chart_accessible", "逐日分数图。三角形表示服务端重算并核对后的报警，叉号表示缺失分数，虚线为阈值。完整数值见逐日记录表。", "Daily score chart. Triangles mark server-recomputed and cross-checked flags, crosses mark missing scores, and a dashed line shows the threshold. Exact values are in the daily records table."],
    ["chart_help", "曲线在缺失分数或缺失日期处断开，不补零或插值。坐标刻度为简写；表格保留原始数值。报警沿用服务端重算并核对后的结果，本页不再次判定。", "Lines break at missing scores or missing dates, without zero filling or interpolation. Axis ticks are abbreviated; the table preserves original values. Flags use the server’s recomputed and cross-checked results; this view does not recalculate them."],
    ["score", "分数", "Score"],
    ["threshold", "阈值", "Threshold"],
    ["threshold_rule", "判定规则（源记录）", "Threshold rule (source record)"],
    ["threshold_source", "阈值来源（源记录）", "Threshold source (source record)"],
    ["alarm", "报警", "Flagged"],
    ["not_flagged", "未标记报警", "Not flagged"],
    ["no_flag", "无报警结果", "No flag result"],
    ["missing", "分数缺失", "Missing score"],
    ["gap", "无逐日源记录", "No daily source record"],
    ["daily", "逐日记录与数据缺口", "Daily records and data gaps"],
    ["day", "源日期", "Source date"],
    ["flag", "阈值标记（服务端重算）", "Threshold flag (server-recomputed)"],
    ["table_help", "日期按源文件的日标签显示，不根据浏览器时区换日。未报警不能证明传感器正常。", "Dates retain the source day label without browser time-zone conversion. An unflagged result does not prove a healthy sensor."],
    ["source_title", "查看计算和来源", "View calculations and sources"],
    ["sources", "来源摘要", "Source summaries"],
    ["source_help", "仅展示服务端提供的文件名、角色和 SHA-256 摘要；不提供原始研究文件下载。", "Only server-provided names, roles and SHA-256 summaries are shown. Original research files are not downloadable here."],
    ["role", "来源角色（原文）", "Source role (original)"],
    ["limitations", "阅读这些结果时的边界", "Limits when interpreting these results"],
    ["unavailable", "未提供", "Not provided"],
    ["unknown_limit", "存在本页尚未识别的限制代码，请核查源摘要。", "An unrecognized limitation code is present. Check the source summary."],
    ["daily_not_realtime", "按日汇总的结果，不是实时监测或即时故障定位。", "Results are daily aggregates, not real-time monitoring or immediate fault localization."],
    ["replay_not_live_inference", "这里只回放已有模型输出；当前没有执行在线模型推断。", "This view replays existing model output. It does not run online model inference."],
    ["injected_not_hardware_truth", "实验中的注入故障不等于已确认的真实硬件损坏。", "Injected faults in an experiment are not confirmed real hardware damage."],
    ["no_payment_link", "研究报警与售后案件、维修验收和付款状态分开保存，不会自动触发交易。", "Research flags are separate from service cases, repair acceptance and payment state. They do not automatically trigger a transaction."],
    ["local_only_unpublished", "这些研究结果仅用于本机查看；尚未确认具备公开发布权限。", "These research results are for local viewing. Permission for public release has not been established."],
    ["threshold_not_field_validated", "此阈值尚未经过真实部署环境的独立验证。", "This threshold has not been independently validated in a deployed field setting."],
    ["retrospective_test_threshold", "阈值来自测试期中故障窗口之外的数据，是回顾性选取，并非部署前完成的标定。", "The threshold was selected retrospectively from test-period data outside fault windows. It is not a pre-deployment calibration."],
    ["clean_not_ground_truth", "clean 仅表示没有注入故障，不代表数据是真值，也不保证传感器没有问题。", "Clean means no fault was injected. It does not mean ground truth or guarantee a healthy sensor."],
    ["scenario_clean", "未注入对照", "Uninjected control"],
    ["scenario_injected", "注入故障", "Injected fault"],
    ["valid_days", "个有效日", "valid days"],
    ["unrounded_fraction", "完整比例数值", "Unrounded fraction"],
    ["conclusion", "这 {valid} 天里，有 {alarms} 天值得进一步检查。", "Worth a closer look on {alarms} of {valid} days."],
    ["conclusion_one", "这一天的结果值得进一步检查。", "This day’s result is worth a closer look."],
    ["conclusion_zero", "这 {valid} 天的结果没有触发提醒。", "No flags were raised across these {valid} days."],
    ["conclusion_zero_one", "这一天的结果没有触发提醒。", "No flag was raised for this day."],
    ["summary_unavailable", "目前还不能可靠地汇总复查天数，请查看下方结果。", "A reliable day count is not available yet. The results are shown below."],
    ["comparison_alarm", "未注入故障的对照中，也有 {alarms} 天报警。所以，报警不等于真实故障。", "The uninjected control also flagged {alarms} days. A flag is not proof of a real fault."],
    ["comparison_alarm_one", "未注入故障的对照中，也有 1 天报警。所以，报警不等于真实故障。", "The uninjected control also flagged 1 day. A flag is not proof of a real fault."],
    ["comparison_clear", "未注入对照在这段时间没有报警，也不能据此认定方法百分之百准确。", "The uninjected control had no flags in this period. That does not establish perfect accuracy."],
    ["result_caution", "报警不等于真实故障；没有报警也不能保证传感器正常。", "A flag is not proof of a real fault. No flag does not guarantee a healthy sensor."],
    ["share", "占有结果天数的 {percent}。", "That is {percent} of days with results."],
    ["missing_summary", "还有数据缺口；没有结果的日子不能当作正常。", "There are also data gaps. Days without results cannot be treated as normal."],
    ["chart_short_help", "三角标记表示值得复查的日子；断开的地方是数据不足。", "Triangles mark days worth reviewing. Breaks in the line indicate missing data."],
    ["daily_signal", "每天的实验分数", "Daily experiment score"],
    ["attention_line", "提醒线", "Flagging threshold"],
    ["worth_checking", "值得复查", "Worth reviewing"],
    ["gap_short", "数据不足", "Missing data"],
    ["calculation_notes", "这些数字怎么算", "How these numbers are reported"],
  ];
  const packs = {en: {}, "zh-CN": {}};
  rows.forEach(([key, zh, en]) => {packs.en[key] = en; packs["zh-CN"][key] = zh;});
  const defaultLimits = ["daily_not_realtime", "replay_not_live_inference", "injected_not_hardware_truth", "no_payment_link", "local_only_unpublished", "threshold_not_field_validated", "retrospective_test_threshold", "clean_not_ground_truth"];
  const element = (tag, className, text) => {const node = document.createElement(tag); if(className)node.className=className; if(text!==undefined)node.textContent=String(text); return node;};
  const append = (parent, ...children) => {children.forEach(child=>parent.append(child)); return parent;};
  const finite = value => typeof value === "number" && Number.isFinite(value) && value >= 0;
  const original = (value, fallback) => ["string", "number"].includes(typeof value) && String(value).trim() ? String(value) : fallback;
  const numeric = (value, fallback) => finite(value) ? String(value) : fallback;
  function day(value) {
    if(typeof value!=="string" || !/^\d{4}-\d{2}-\d{2}(?:$|T)/.test(value))return null;
    const label=value.slice(0,10),time=Date.parse(label+"T00:00:00Z");
    return Number.isFinite(time) && new Date(time).toISOString().slice(0,10)===label ? {label,time} : null;
  }
  const dayLabel = time => new Date(time).toISOString().slice(0,10);
  function displayTitle(dataset,t) {
    const title=original(dataset.title,dataset.id);
    const match=/^(.+?) - (clean|injected)$/.exec(title);
    return match && match[2]===dataset.scenario_code ? match[1]+" · "+t("scenario_"+dataset.scenario_code) : title;
  }
  function normalized(dataset) {
    if(!dataset || !["research_output_with_injected_faults", "synthetic_contract_fixture"].includes(dataset.provenance) || dataset.cadence!=="daily" || !finite(dataset.threshold) || !Array.isArray(dataset.points))return null;
    const start=day(dataset.window?.start),end=day(dataset.window?.end);
    if(!start || !end || start.time>end.time)return null;
    const points=[],seen=new Set();
    for(const point of dataset.points){
      const date=day(point?.t);
      if(!date || date.time<start.time || date.time>end.time || seen.has(date.label) || !(point.score===null || finite(point.score)) || ![true,false,null].includes(point.alarm) || (point.score===null && point.alarm!==null))return null;
      seen.add(date.label);points.push({label:date.label,time:date.time,score:point.score,alarm:point.alarm});
    }
    points.sort((a,b)=>a.time-b.time);
    return {start,end,points};
  }
  function message(parent, title, help) {
    const box=element("div","research-message");box.setAttribute("role","status");
    append(box,element("h2","",title));if(help)box.append(element("p","",help));parent.append(box);
  }
  function renderInference(page, result, locale) {
    if(!result || result.status==="unconfigured")return;
    const zh=locale==="zh-CN";
    const card=element("article","research-card");card.id="local-inference-result";
    card.append(element("h2","",zh?"冻结模型本机运行记录":"Local frozen-model run"));
    if(result.status!=="complete" || result.mode!=="local_frozen_model_inference" || result.model_executed!==true){
      card.append(element("p","research-boundary",zh?"暂时没有可核验的运行记录，不能据此确认模型已运行。":"No verified run record is available. Model execution cannot be confirmed."));
      page.append(card);return;
    }
    card.append(element("p","",zh?"模型已在本机重新计算历史输入，并与保存的预测逐日核对。刷新页面只读取这份运行记录，不会重新运行模型。":"The model recomputed historical inputs locally and checked predictions against saved results, day by day. Refreshing this page only reads that run record."));
    card.append(element("p","research-boundary",zh?"这仍是历史数据验证，尚未接入日常售后案件；不代表实时诊断、硬件损坏确认或准确率。研究数据的公开权限尚未确认。":"This is historical-data verification, separate from daily service cases. It does not establish live diagnosis, hardware damage or accuracy. Public release of research data is not cleared."));
    const format=new Intl.NumberFormat(locale,{maximumSignificantDigits:5});
    const items=element("ul","research-help");
    items.append(element("li","",`${result.model.name} · CPU · ${result.model.feature_count} ${zh?"个特征":"features"} · ${result.model.lookback_days} ${zh?"天输入窗口":"days of input"}`));
    for(const run of result.comparison){
      const name=run.variant==="clean"?(zh?"未注入对照":"Uninjected control"):(zh?"注入故障":"Injected fault");
      items.append(element("li","",zh?`${name}：核对 ${run.compared_points} 天，${run.matched?"在容差内一致":"未通过一致性核查"}；最大预测差 ${format.format(run.max_prediction_difference)} VWC 百分点。`:`${name}: ${run.compared_points} days checked, ${run.matched?"matched within tolerance":"consistency check failed"}; maximum prediction difference ${format.format(run.max_prediction_difference)} VWC percentage points.`));
    }
    card.append(items);
    const details=element("details","research-sources");details.append(element("summary","",zh?"查看运行时间与来源摘要":"Run time and source fingerprints"));
    details.append(element("p","",`${result.completed_at} · ${result.run_id}`));
    for(const source of result.sources)details.append(element("p","method",`${source.role}: ${source.sha256}`));
    card.append(details);page.append(card);
  }
  function render(container, payload, locale="en", inference=null) {
    if(!(container instanceof Element))throw new TypeError("Research render requires an Element container");
    const requestedLocale=locale;
    locale=locale==="zh-CN"?"zh-CN":"en";
    const t=(key,params={})=>(packs[locale][key]||packs.en[key]).replace(/\{(\w+)\}/g,(_,name)=>String(params[name]??"{"+name+"}"));
    const state=instances.get(container)||{selected:null,sourcesOpen:false,observer:null};
    state.observer?.disconnect();instances.set(container,state);
    const page=element("section","research-view");
    append(page,element("h1","",t("title")),element("p","intro",t("intro")),element("p","research-boundary",t("boundary")));
    container.replaceChildren(page);
    if(!["en","zh-CN"].includes(requestedLocale))page.prepend(element("p","method",window.FieldFixI18n.text(requestedLocale,"research_language_fallback")));
    renderInference(page,inference,locale);
    if(payload?.status==="unconfigured"){message(page,t("unconfigured"),t("unconfigured_help"));return;}
    if(payload?.status!=="ready" || payload.mode!=="precomputed_research_replay" || !Array.isArray(payload.datasets)){message(page,t("invalid"),t("invalid_help"));return;}
    if(!payload.datasets.length){message(page,t("empty"));return;}
    if(payload.datasets.some(dataset=>!dataset || typeof dataset.id!=="string" || !dataset.id) || new Set(payload.datasets.map(dataset=>dataset.id)).size!==payload.datasets.length){message(page,t("invalid"),t("invalid_help"));return;}
    if(!payload.datasets.some(dataset=>dataset.id===state.selected))state.selected=payload.datasets[0].id;
    const label=element("label","research-select-label",t("choose"));label.htmlFor="research-dataset";
    const select=element("select","form-select");select.id="research-dataset";
    for(const dataset of payload.datasets){const option=element("option","",displayTitle(dataset,t));option.value=dataset.id;select.append(option);}
    select.value=state.selected;select.addEventListener("change",()=>{state.selected=select.value;render(container,payload,locale,inference);});
    page.append(append(element("div","research-selector"),label,select));
    const dataset=payload.datasets.find(item=>item.id===state.selected),data=normalized(dataset);
    if(!data){message(page,t("invalid"),t("invalid_help"));return;}
    const card=element("article","research-card");card.id="research-result";
    if(dataset.provenance==="synthetic_contract_fixture")card.append(element("p","research-provenance",t(dataset.provenance)));
    renderSummary(card,dataset,data,payload.datasets,locale,t);
    page.append(card);renderChart(card,dataset,data,state,t);
    renderSources(page,dataset,data,state,t);
  }
  function summaryCounts(dataset,data) {
    const valid=dataset.metrics?.valid_points,alarms=dataset.metrics?.alarm_points;
    const scored=data.points.filter(point=>point.score!==null);
    if(!Number.isInteger(valid) || valid<=0 || !Number.isInteger(alarms) || alarms<0 || alarms>valid || scored.length!==valid || scored.some(point=>point.alarm===null) || scored.filter(point=>point.alarm===true).length!==alarms)return null;
    return {valid,alarms};
  }
  function renderSummary(card,dataset,data,datasets,locale,t) {
    if(!data.points.some(point=>point.score!==null))return;
    const counts=summaryCounts(dataset,data);
    if(!counts){card.append(element("p","research-help",t("summary_unavailable")));return;}
    const key=counts.alarms===0?(counts.valid===1?"conclusion_zero_one":"conclusion_zero"):(counts.valid===1?"conclusion_one":"conclusion");
    const conclusion=element("h2","research-conclusion",t(key,counts));conclusion.id="research-conclusion";card.append(conclusion);
    let caution=t("result_caution");
    const group=/^(.+)-(clean|injected)$/.exec(dataset.id);
    const control=dataset.scenario_code==="clean"?dataset:group?datasets.find(item=>item.id===group[1]+"-clean" && item.scenario_code==="clean"):null;
    const controlData=control?normalized(control):null,controlCounts=controlData?summaryCounts(control,controlData):null;
    if(controlCounts && control.model===dataset.model && control.threshold===dataset.threshold && controlData.start.time===data.start.time && controlData.end.time===data.end.time){
      caution=t(controlCounts.alarms===0?"comparison_clear":controlCounts.alarms===1?"comparison_alarm_one":"comparison_alarm",controlCounts);
    }
    const comparison=element("p","research-comparison",caution);comparison.id="research-control-note";card.append(comparison);
    const fraction=dataset.metrics?.alarm_fraction;
    if(finite(fraction) && fraction<=1){
      const percent=new Intl.NumberFormat(locale,{style:"percent",maximumFractionDigits:1}).format(fraction);
      const share=element("p","research-share",t("share",{percent}));share.title=t("unrounded_fraction")+": "+String(fraction);card.append(share);
    }
    if(dataset.metrics?.missing_points>0 || data.points.length<(data.end.time-data.start.time)/DAY+1)card.append(element("p","research-help",t("missing_summary")));
  }
  function renderChart(card,dataset,data,state,t) {
    const figure=element("figure","research-figure");
    figure.append(element("h3","",t("chart_title")));
    const description=element("figcaption","research-help",t("chart_short_help"));description.id="research-chart-help";
    if(!data.points.length){message(figure,t("no_points"));figure.append(description);card.append(figure);return;}
    if(!data.points.some(point=>point.score!==null)){message(figure,t("no_valid"));figure.append(description);card.append(figure);return;}
    const wrap=element("div","research-chart-wrap"),canvas=element("canvas");canvas.id="research-chart";
    canvas.setAttribute("role","img");canvas.setAttribute("aria-label",t("chart_accessible"));canvas.setAttribute("aria-describedby",description.id);
    wrap.append(canvas);figure.append(wrap);
    const legend=element("div","research-legend");
    const keys=[["daily_signal","line"],["attention_line","dash"],["worth_checking","triangle"]];
    if(data.points.some(point=>point.score===null))keys.push(["gap_short","cross"]);
    for(const [key,shape] of keys){
      const symbol=element("i","research-key-"+shape);symbol.setAttribute("aria-hidden","true");
      legend.append(append(element("span"),symbol,element("span","",t(key))));
    }
    append(figure,legend,description);card.append(figure);
    const redraw=()=>{if(canvas.isConnected && canvas.getBoundingClientRect().width>0)draw(canvas,dataset,data,t);};
    if(typeof ResizeObserver!=="undefined"){state.observer=new ResizeObserver(redraw);state.observer.observe(wrap);}
    requestAnimationFrame(redraw);
  }
  function draw(canvas,dataset,data,t) {
    const rect=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;
    if(rect.width<1 || rect.height<1)return;
    canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);
    const ctx=canvas.getContext("2d");if(!ctx)return;
    ctx.scale(ratio,ratio);
    const width=rect.width,height=rect.height,left=60,right=14,top=18,bottom=35;
    const plotWidth=Math.max(1,width-left-right),plotHeight=Math.max(1,height-top-bottom);
    const style=getComputedStyle(canvas),color=key=>style.getPropertyValue("--research-"+key).trim();
    const values=data.points.filter(point=>point.score!==null).map(point=>point.score);
    const highest=Math.max(dataset.threshold,...values);
    const ceiling=highest>0?Math.min(Number.MAX_VALUE,highest+highest*.12):1;
    const start=data.start.time,end=Math.max(start+DAY,data.end.time);
    const x=time=>left+plotWidth*(time-start)/(end-start),y=value=>top+plotHeight*(1-value/ceiling);
    const short=value=>value===0?"0":Number(value.toPrecision(3)).toString();
    ctx.font='11px "Segoe UI", sans-serif';ctx.lineWidth=1;
    for(let i=0;i<=4;i++){
      const value=ceiling*(i/4),py=y(value);
      ctx.strokeStyle=color("grid");ctx.beginPath();ctx.moveTo(left,py);ctx.lineTo(width-right,py);ctx.stroke();
      ctx.fillStyle=color("muted");ctx.textAlign="right";ctx.fillText(short(value),left-8,py+4);
    }
    ctx.save();ctx.strokeStyle=color("threshold");ctx.lineWidth=1.5;ctx.setLineDash([6,4]);
    ctx.beginPath();ctx.moveTo(left,y(dataset.threshold));ctx.lineTo(width-right,y(dataset.threshold));ctx.stroke();ctx.restore();
    ctx.strokeStyle=color("score");ctx.lineWidth=2;ctx.beginPath();let previous=null;
    for(const point of data.points){
      if(point.score===null){previous=null;continue;}
      if(previous && point.time-previous.time===DAY)ctx.lineTo(x(point.time),y(point.score));
      else ctx.moveTo(x(point.time),y(point.score));
      previous=point;
    }
    ctx.stroke();
    for(const point of data.points){
      const px=x(point.time);
      if(point.score===null){
        const py=top+plotHeight;ctx.strokeStyle=color("muted");ctx.lineWidth=1.5;ctx.beginPath();
        ctx.moveTo(px-3,py-3);ctx.lineTo(px+3,py+3);ctx.moveTo(px-3,py+3);ctx.lineTo(px+3,py-3);ctx.stroke();continue;
      }
      const py=y(point.score);ctx.beginPath();
      if(point.alarm===true){ctx.fillStyle=color("alarm");ctx.moveTo(px,py-5);ctx.lineTo(px-5,py+4);ctx.lineTo(px+5,py+4);ctx.closePath();}
      else {ctx.fillStyle=color("score");ctx.arc(px,py,2.5,0,Math.PI*2);}
      ctx.fill();
    }
    ctx.fillStyle=color("muted");ctx.textAlign="left";ctx.fillText(data.start.label,left,height-9);
    if(data.end.time!==data.start.time){ctx.textAlign="right";ctx.fillText(data.end.label,width-right,height-9);}
    if(width>=650 && data.end.time-data.start.time>DAY*2){const midpoint=Math.floor((data.start.time+data.end.time)/2/DAY)*DAY;ctx.textAlign="center";ctx.fillText(dayLabel(midpoint),x(midpoint),height-9);}
  }
  function renderTable(card,data,state,t) {
    const details=element("section","research-daily-section");details.id="research-daily-records";
    append(details,element("h3","",t("daily")),element("p","research-help",t("table_help")));
    const table=element("table","research-table"),head=element("thead"),header=element("tr"),body=element("tbody");
    for(const key of ["day","score","flag"]){const cell=element("th","",t(key));cell.scope="col";header.append(cell);}
    head.append(header);
    const gap=(start,end)=>{
      if(start>end)return;
      const row=element("tr","research-row-gap"),range=dayLabel(start)+(start===end?"":" — "+dayLabel(end));
      append(row,element("td","",range),element("td","",t("unavailable")),element("td","",t("gap")));body.append(row);
    };
    let nextDay=data.start.time;
    for(const point of data.points){
      gap(nextDay,point.time-DAY);nextDay=point.time+DAY;
      const status=point.score===null?"missing":point.alarm===true?"alarm":point.alarm===false?"not_flagged":"no_flag";
      const row=element("tr",point.alarm===true?"research-row-alarm":point.score===null?"research-row-gap":"");
      append(row,element("td","",point.label),element("td","research-number",numeric(point.score,t("unavailable"))),element("td","",(point.alarm===true?"▲ ":"")+t(status)));body.append(row);
    }
    gap(nextDay,data.end.time);
    append(table,head,body);details.append(table);card.append(details);
  }
  function renderSources(page,dataset,data,state,t) {
    const details=element("details","research-card research-details research-sources");details.id="research-source-details";details.open=state.sourcesOpen;
    details.addEventListener("toggle",()=>{state.sourcesOpen=details.open;});
    append(details,element("summary","",t("source_title")),element("p","research-provenance",t(dataset.provenance)),element("p","research-help",t("no_link")));
    const meta=element("dl","research-meta");
    for(const [key,value] of [["model",dataset.model],["score_name",dataset.score_name],["scenario",dataset.scenario_code],["window",data.start.label+" — "+data.end.label]]){
      meta.append(append(element("div"),element("dt","",t(key)),element("dd","",original(value,t("unavailable")))));
    }
    details.append(meta);details.append(element("h3","",t("calculation_notes")));
    const metrics=element("dl","research-meta");
    for(const key of ["points","valid_points","missing_points","alarm_points","alarm_fraction"]){
      metrics.append(append(element("div"),element("dt","",t(key)),element("dd","",numeric(dataset.metrics?.[key],t("unavailable")))));
    }
    details.append(metrics);
    const threshold=element("dl","research-threshold");
    for(const [key,value] of [["threshold",dataset.threshold],["threshold_rule",dataset.threshold_rule],["threshold_source",dataset.threshold_source]]){
      threshold.append(append(element("div"),element("dt","",t(key)),element("dd","",original(value,t("unavailable")))));
    }
    append(details,threshold,element("p","research-help",t("chart_help")));
    renderTable(details,data,state,t);
    append(details,element("h3","",t("sources")),element("p","research-help",t("source_help")));
    const list=element("ul","research-source-list");
    const sources=Array.isArray(dataset.sources)?dataset.sources:[];
    if(!sources.length)list.append(element("li","",t("unavailable")));
    for(const source of sources){
      const item=element("li");item.append(element("strong","research-source-name",original(source?.name,t("unavailable"))));
      item.append(element("p","",t("role")+": "+original(source?.role,t("unavailable"))));
      const hash=typeof source?.sha256==="string" && /^[a-fA-F0-9]{64}$/.test(source.sha256)?source.sha256:t("unavailable");
      item.append(append(element("p","research-hash"),element("span","","SHA-256: "),element("code","",hash)));list.append(item);
    }
    details.append(list);details.append(element("h3","",t("limitations")));
    const limits=element("ul","research-limitations");
    const supplied=Array.isArray(dataset.limitations)&&dataset.limitations.length?dataset.limitations:defaultLimits;
    let unknown=false;
    for(const code of new Set(supplied)){
      if(defaultLimits.includes(code))limits.append(element("li","",t(code)));else unknown=true;
    }
    if(unknown)limits.append(element("li","",t("unknown_limit")));
    details.append(limits);page.append(details);
  }
  return Object.freeze({render});
})();
