
(function(){
  const CATEGORY_BY_TITLE={
    "무조건 암기":"must_memorize","이해 필수":"must_understand","출제 핫스팟":"exam_hotspots",
    "헷갈리는 비교":"confusing_pairs","공식·프레임워크":"formula_or_frameworks"
  };
  const safe=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
  const nl=s=>safe(s).replace(/\n/g,"<br>");
  let modal=null;
  function ensureModal(){
    if(modal)return modal;
    const style=document.createElement("style");
    style.textContent=`
    #coreDetailModal{position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.55);display:flex;align-items:flex-end;justify-content:center;padding:12px}
    #coreDetailModal.hidden{display:none!important}.core-detail-sheet{width:min(760px,100%);max-height:88vh;overflow:auto;background:#fff;border-radius:24px 24px 18px 18px;padding:20px;box-shadow:0 24px 80px rgba(15,23,42,.28)}
    .core-detail-head{display:flex;gap:12px;align-items:flex-start;justify-content:space-between;position:sticky;top:-20px;background:#fff;padding:4px 0 12px;z-index:2}
    .core-detail-close{flex:0 0 auto;background:#f1f5f9;color:#0f172a;width:38px;height:38px;padding:0;border-radius:50%;font-size:20px}
    .core-detail-answer{line-height:1.75;font-size:15px}.core-detail-sources{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}
    .core-detail-source{background:#eef2ff;color:#3730a3;border-radius:999px;padding:6px 9px;font-size:11px;font-weight:800}
    #sumBody .core-detail-item{cursor:pointer;border-radius:14px;padding:13px 10px;transition:.15s;background:linear-gradient(90deg,#fff,#fbfcff)}
    #sumBody .core-detail-item:hover{background:#f8fafc}#sumBody .core-detail-item:active{transform:scale(.995)}
    .core-detail-hint{font-size:10px;color:#6366f1;font-weight:850;margin-top:5px}.core-detail-loading{padding:28px 0;text-align:center;color:#64748b}
    @media(min-width:700px){#coreDetailModal{align-items:center}.core-detail-sheet{border-radius:24px}}`;
    document.head.appendChild(style);
    modal=document.createElement("div");modal.id="coreDetailModal";modal.className="hidden";
    modal.innerHTML=`<div class="core-detail-sheet" role="dialog" aria-modal="true">
      <div class="core-detail-head"><div><div class="mini" id="coreDetailCategory">시험 핵심 상세설명</div><h2 id="coreDetailTitle" style="margin-top:4px"></h2></div><button class="core-detail-close" aria-label="닫기">×</button></div>
      <div id="coreDetailBody" class="core-detail-answer"></div><div id="coreDetailSources" class="core-detail-sources"></div></div>`;
    document.body.appendChild(modal);
    modal.querySelector(".core-detail-close").onclick=()=>modal.classList.add("hidden");
    modal.addEventListener("click",e=>{if(e.target===modal)modal.classList.add("hidden")});
    return modal;
  }
  async function openDetail(category,index){
    const m=ensureModal(),item=(typeof A!=="undefined"&&A&&A[category])?A[category][index]:null;
    document.querySelector("#coreDetailCategory").textContent="시험 핵심 상세설명";
    document.querySelector("#coreDetailTitle").textContent=item?.text||"상세설명";
    document.querySelector("#coreDetailBody").innerHTML=`<div class="core-detail-loading">강의자료에서 근거를 찾아 상세설명 만드는 중…</div>`;
    document.querySelector("#coreDetailSources").innerHTML="";m.classList.remove("hidden");
    try{
      const x=await jf(`/api/p/${PID}/courses/${CID}/core-detail`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({category,index})});
      document.querySelector("#coreDetailCategory").textContent=x.category||"시험 핵심";
      document.querySelector("#coreDetailTitle").textContent=x.title||item?.text||"상세설명";
      document.querySelector("#coreDetailBody").innerHTML=nl(x.answer||"설명이 없어.");
      document.querySelector("#coreDetailSources").innerHTML=(x.sources||[]).map(s=>`<span class="core-detail-source">${safe(s.doc)}${s.page?` · p.${s.page}`:""}</span>`).join("");
    }catch(e){document.querySelector("#coreDetailBody").innerHTML=`<div class="notice">상세설명을 불러오지 못했어: ${safe(e.message||e)}</div>`}
  }
  function enhance(){
    const root=document.querySelector("#sumBody");if(!root)return;
    let category=null;const counters={};
    [...root.children].forEach(el=>{
      if(el.tagName==="H3"){category=CATEGORY_BY_TITLE[(el.textContent||"").trim()]||null;if(category&&counters[category]==null)counters[category]=0;return}
      if(!category||!el.classList.contains("item"))return;
      const cat=category,idx=counters[cat]++;
      if(el.dataset.coreDetailBound==="1")return;
      el.dataset.coreDetailBound="1";el.classList.add("core-detail-item");
      const hint=document.createElement("div");hint.className="core-detail-hint";hint.textContent="눌러서 상세설명 보기 ›";el.appendChild(hint);
      el.addEventListener("click",()=>openDetail(cat,idx));
    });
  }
  window.addEventListener("keydown",e=>{if(e.key==="Escape"&&modal)modal.classList.add("hidden")});
  function start(){ensureModal();const root=document.querySelector("#sumBody");if(root)new MutationObserver(enhance).observe(root,{childList:true,subtree:true});enhance();setInterval(enhance,1200)}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start);else start();
})();
