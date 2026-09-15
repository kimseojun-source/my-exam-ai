// Preserve the existing API, session cookie and local-storage keys.
let viewEpoch=0,profilesById=new Map();
const originalJf=jf;
jf=async function(url,opt={}){
  const match=url.match(/^\/api\/p\/(\d+)(?:\/courses\/(\d+))?/);
  const result=await originalJf(url,opt);
  if(match && (Number(match[1])!==PID || (match[2] && Number(match[2])!==CID)))
    throw Error('과목이 전환되어 이전 요청의 화면 갱신을 중단했어. 결과는 원래 과목에 보관돼.');
  return result;
};
loadProfiles=async function(){
  const ps=await jf('/api/profiles');profilesById=new Map(ps.map(p=>[p.id,p]));
  $('#profiles').innerHTML=ps.map(p=>`<button class="profile" data-profile-id="${p.id}"><div class="avatar">${esc((p.name||'U')[0])}</div><b>${esc(p.name)}</b><div class="mini">${p.is_owner?'소유자':'사용자'} · ${p.has_pin?'PIN 보호':'PIN 미설정'}</div></button>`).join('');
  $('#guestAdmin').classList.toggle('hidden',!PROFILE?.is_owner || ps.length>=2);
};
$('#profiles').addEventListener('click',e=>{const b=e.target.closest('[data-profile-id]');if(b)enterProfile(profilesById.get(+b.dataset.profileId));});
function resetCourseView(){
  QUIZ=null;CARDS=[];CI=0;CB=false;COURSE=null;A={};
  for(const id of ['chat','ask','quizBody','sumBody','extBody','patternBody','cardBox','documentList','uploadStatus']){const el=$('#'+id);if(el.tagName==='TEXTAREA')el.value='';else el.innerHTML='';}
  $('#files').value='';$('#coreDetailModal')?.classList.add('hidden');
  pane('dash',document.querySelector('.tab'));
}
openCourse=async function(id){
  const epoch=++viewEpoch;CID=id;resetCourseView();$('#ws').classList.add('hidden');
  try{
    const course=await jf(`/api/p/${PID}/courses/${id}`);
    if(epoch!==viewEpoch || CID!==id)return;
    COURSE=course;A=course.analysis||{};$('#empty').classList.add('hidden');$('#ws').classList.remove('hidden');$('#ctitle').textContent=course.name;render();await loadCourses();
    sessionStorage.setItem(`forest_course_${PID}`,String(id));
  }catch(e){if(epoch===viewEpoch)alert(e.message);}
};
const originalSwitch=switchProfile;
switchProfile=async function(){++viewEpoch;resetCourseView();await originalSwitch();};
const originalShow=showApp;
showApp=function(){originalShow();$('#guestAdmin').classList.toggle('hidden',!PROFILE.is_owner || profilesById.size>=2);};
const originalRender=render;
render=function(){
  // Clear stale history even for a course without analysis; tutor works independently.
  $('#chat').innerHTML=(COURSE.tutor_history||[]).map(m=>`<div class="bubble ${m.role==='user'?'me':'ai'}">${esc(m.content)}</div>`).join('');
  renderPattern(COURSE.exam_pattern);originalRender();
  $('#documentList').innerHTML=COURSE.documents.map(d=>`<div class="document"><b>${esc(d.name)}</b><div class="src">${d.pages}p · ${d.extraction==='pending_vision'?'원본 보관 · AI 읽기 대기':esc(d.extraction)}</div><div class="row"><button class="ghost" data-download="${d.id}">원본 받기</button><button class="soft" data-reprocess="${d.id}">다시 읽기</button></div></div>`).join('');
};
async function busy(button,action){
  if(button?.disabled)return;const text=button?.textContent;
  if(button){button.disabled=true;button.textContent='처리 중…';}
  try{return await action();}catch(e){alert(e.message);}finally{if(button){button.disabled=false;button.textContent=text;}}
}
$('#documentList').addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  const base=`/api/p/${PID}/courses/${CID}/documents/`;
  busy(b,async()=>{
    if(b.dataset.download)await downloadFile(base+b.dataset.download+'/file');
    else {await jf(base+b.dataset.reprocess+'/reprocess',{method:'POST'});await openCourse(CID);}
  });
});
async function downloadFile(url,name){
  // Normal authenticated navigation also works with Android's DownloadListener.
  if(!ACCESS){const a=document.createElement('a');a.href=url;if(name)a.download=name;document.body.appendChild(a);a.click();a.remove();return;}
  const r=await fetch(url,{headers:{'X-App-Code':ACCESS}});if(!r.ok)throw Error('파일 다운로드에 실패했어.');
  const blob=await r.blob();const href=URL.createObjectURL(blob),a=document.createElement('a');a.href=href;a.download=name||'FOR-EST-document';a.click();setTimeout(()=>URL.revokeObjectURL(href),30000);
}
backup=async function(){try{await downloadFile(`/api/p/${PID}/backup`,`FOR-EST-${PROFILE.name}-backup.json`);}catch(e){alert(e.message);}};
uploadDocs=async function(){
  const files=[...$('#files').files],pid=PID,cid=CID;
  if(!files.length)return alert('PDF 또는 이미지를 골라줘.');
  if(files.length>15)return alert('한 번에 15개까지 올릴 수 있어.');
  if(files.some(f=>f.size>40*1024*1024))return alert('파일당 40MB까지 올릴 수 있어.');
  const fd=new FormData();files.forEach(f=>fd.append('files',f));fd.append('document_type',$('#dtype').value);
  const button=document.querySelector('[onclick="uploadDocs()"]');
  await busy(button,async()=>{
    $('#uploadStatus').textContent='자료를 업로드하고 읽는 중이야. 이미지·스캔 PDF는 시간이 조금 걸릴 수 있어.';
    try{
      const x=await jf(`/api/p/${pid}/courses/${cid}/documents`,{method:'POST',body:fd});
      if(PID!==pid||CID!==cid)return;
      const messages=[...x.added.map(d=>`${d.name}: ${d.warning||'추가 완료'}`),...(x.skipped||[]).map(d=>`${d.name}: 이미 보관된 자료`),...(x.errors||[]).map(d=>`${d.name}: ${d.message}`)];
      await openCourse(cid);$('#uploadStatus').textContent=messages.join('\n');
    }catch(e){if(PID===pid&&CID===cid)$('#uploadStatus').textContent=e.message;throw e;}
  });
};
// Keep all long operations bound to the course that started them.
for(const name of ['analyze','makeQuiz','analyzePattern','gradeQuiz','askTutor']){
  const original=window[name];
  window[name]=async function(){const b=document.querySelector(`[onclick="${name}()"]`);return busy(b,()=>original());};
}
askTutor=async function(){
  const q=$('#ask').value.trim(),pid=PID,cid=CID;if(!q)return;
  const button=document.querySelector('[onclick="askTutor()"]');
  await busy(button,async()=>{
    $('#chat').innerHTML+=`<div class="bubble me">${esc(q)}</div><div class="bubble ai" id="thinking">현재 과목 자료에서 근거를 찾는 중…</div>`;$('#ask').value='';
    try{
      const x=await jf(`/api/p/${pid}/courses/${cid}/tutor`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
      $('#thinking')?.remove();$('#chat').innerHTML+=`<div class="bubble ai">${esc(x.answer)}</div>`;$('#chat').scrollTop=$('#chat').scrollHeight;
    }catch(e){if(PID===pid&&CID===cid){$('#thinking')?.remove();$('#ask').value=q;}throw e;}
  });
};
function syncViewport(){document.documentElement.style.setProperty('--app-h',`${window.visualViewport?.height||innerHeight}px`);}
window.addEventListener('resize',syncViewport,{passive:true});window.addEventListener('orientationchange',syncViewport,{passive:true});window.visualViewport?.addEventListener('resize',syncViewport,{passive:true});syncViewport();

function setupInstallHelp(){
  const ua=navigator.userAgent||'',isIOS=/iPad|iPhone|iPod/.test(ua)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
  const standalone=window.matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;
  if(!isIOS||standalone)return;
  const dismissed=Number(localStorage.getItem('forest_install_dismissed')||0);
  if(Date.now()-dismissed<3*24*60*60*1000)return;
  const safari=/Safari/.test(ua)&&!/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
  const banner=document.createElement('aside');banner.className='install-banner';banner.setAttribute('aria-label','FOR EST 홈 화면 설치 안내');
  banner.innerHTML=`<img src="/icons/apple-touch-icon.png" alt=""><div class="install-banner-copy"><b>FOR'EST를 앱처럼 설치</b><span>${safari?'Safari 공유 버튼에서 바로 추가할 수 있어.':'Safari에서 열면 홈 화면에 추가할 수 있어.'}</span></div><button class="install-open">설치 방법</button><button class="install-close" aria-label="설치 안내 닫기">×</button>`;
  document.body.appendChild(banner);
  const close=()=>{banner.remove();localStorage.setItem('forest_install_dismissed',String(Date.now()));};
  banner.querySelector('.install-close').addEventListener('click',close);
  banner.querySelector('.install-open').addEventListener('click',()=>{
    const modal=document.createElement('div');modal.className='install-sheet-backdrop';modal.setAttribute('role','dialog');modal.setAttribute('aria-modal','true');modal.setAttribute('aria-label','iPhone 및 iPad 설치 방법');
    modal.innerHTML=`<section class="install-sheet"><div class="install-sheet-head"><img src="/icons/apple-touch-icon.png" alt="FOR'EST 아이콘"><div><h2>홈 화면에 FOR'EST 추가</h2><div class="sub">한 번 추가하면 일반 앱처럼 전체 화면으로 열려.</div></div></div>${safari?'<div class="install-steps"><div class="install-step"><div>Safari 아래쪽의 <b>공유</b> 버튼(□↑)을 눌러.</div></div><div class="install-step"><div><b>홈 화면에 추가</b>를 선택해.</div></div><div class="install-step"><div>이름이 FOR\'EST인지 보고 <b>추가</b>를 눌러.</div></div></div>':'<div class="install-steps"><div class="install-step"><div>오른쪽 아래 메뉴에서 <b>Safari에서 열기</b>를 선택해.</div></div><div class="install-step"><div>Safari의 <b>공유</b> 버튼(□↑)을 눌러.</div></div><div class="install-step"><div><b>홈 화면에 추가</b>를 선택해.</div></div></div>'}<div class="install-sheet-actions">${safari?'':'<button class="soft install-copy">주소 복사</button>'}<button class="primary install-done">확인</button></div></section>${safari?'<div class="install-share-arrow" aria-hidden="true">↓</div>':''}`;
    document.body.appendChild(modal);
    const done=()=>{modal.remove();banner.remove();localStorage.setItem('forest_install_dismissed',String(Date.now()));};
    modal.querySelector('.install-done').addEventListener('click',done);
    modal.addEventListener('click',e=>{if(e.target===modal)done();});
    modal.querySelector('.install-copy')?.addEventListener('click',async e=>{try{await navigator.clipboard.writeText(location.href);e.currentTarget.textContent='주소 복사됨';}catch(_){prompt('주소를 복사해 Safari에서 열어줘',location.href);}});
  });
}
setupInstallHelp();
(async()=>{
  try{
    await loadProfiles();await restoreSession();
    const runtime=await jf('/api/runtime');
    if(!runtime.ai_configured){$('#aiStatus').textContent='AI 연결 전이야. PDF 기본 정리와 원본 보관은 사용할 수 있어. 이미지·스캔 자료 읽기와 AI 질문은 연결 후 이용할 수 있어.';$('#aiStatus').classList.remove('hidden');}
  }catch(e){$('#profiles').textContent=`연결하지 못했어: ${e.message}. 새로고침해서 다시 시도해줘.`;}
})();
