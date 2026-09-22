/* Study-first shell. Existing controls and private API authorization are preserved. */
(()=>{
 const ws=document.querySelector('#ws'),side=document.querySelector('.side'),management=ws.firstElementChild;
 const visibility=document.createElement('style');visibility.textContent='#ws.hidden{display:none!important}';document.head.append(visibility);
 const header=management.firstElementChild;
 const drawer=document.createElement('dialog');drawer.id='studyDrawer';drawer.setAttribute('aria-label','과목과 자료 관리');
 drawer.innerHTML='<div class="drawer-head"><h2>과목 · 자료 관리</h2><button type="button" data-close-drawer aria-label="메뉴 닫기">닫기 ×</button></div>';
 document.body.append(drawer);drawer.append(side,management);
 drawer.querySelector('[data-close-drawer]').onclick=()=>drawer.close();
 const top=document.querySelector('#app .top'),menu=document.createElement('button');menu.type='button';menu.textContent='☰';menu.setAttribute('aria-label','과목과 자료 메뉴');menu.setAttribute('aria-haspopup','dialog');top.prepend(menu);
 function openMenu(){drawer.showModal();}menu.onclick=openMenu;
 const shell=document.createElement('div');shell.className='study-split';
 shell.innerHTML='<section class="study-source" aria-label="원본 자료"><div class="source-tools"><select id="sourceDocument" aria-label="자료 선택"></select><div class="source-pages"><button data-prev aria-label="이전 페이지">‹</button><input id="sourcePage" type="number" min="1" aria-label="페이지 번호"><span id="sourceCount"></span><button data-next aria-label="다음 페이지">›</button><button data-pen>필기</button></div></div><div id="sourceStage" tabindex="0"></div></section><div class="study-divider"><input type="range" min="30" max="65" value="45" aria-label="자료 영역 너비"></div><section class="study-explanation" aria-label="설명과 학습"></section>';
 const right=shell.querySelector('.study-explanation');
 [...ws.children].forEach(el=>right.append(el));ws.append(header,shell);header.classList.add('study-course-header');
 const mobile=document.createElement('div');mobile.className='study-mobile-tabs';mobile.innerHTML='<button data-view="source">자료</button><button data-view="explanation">설명 · 학습</button>';header.after(mobile);
 mobile.onclick=e=>{const b=e.target.closest('[data-view]');if(b){shell.dataset.view=b.dataset.view;mobile.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));}};
 shell.dataset.view='explanation';mobile.querySelector('[data-view="explanation"]').setAttribute('aria-pressed','true');
 shell.querySelector('input[type=range]').oninput=e=>shell.style.setProperty('--source-width',e.target.value+'%');
 let doc=null,page=1,url=null,request=null,epoch=0;
 const select=document.querySelector('#sourceDocument'),input=document.querySelector('#sourcePage'),stage=document.querySelector('#sourceStage');
 const key=()=>`forest_reading_${PID}_${CID}`;
 function saved(){try{return JSON.parse(localStorage.getItem(key())||'{}');}catch{return {};}}
 function persist(){if(doc)try{localStorage.setItem(key(),JSON.stringify({document:doc.id,page}));}catch{}}
 async function showPage(){
  const turn=++epoch;request?.abort();if(url){URL.revokeObjectURL(url);url=null;}
  shell.querySelector('[data-pen]').disabled=!doc;
  if(!doc){stage.innerHTML='<div class="source-empty"><h2>첫 자료를 추가해</h2><p>PDF나 사진을 올리면 여기에서 설명과 함께 볼 수 있어.</p><button data-add>자료 추가하기</button></div>';stage.querySelector('[data-add]').onclick=openMenu;select.disabled=true;input.disabled=true;input.value='';document.querySelector('#sourceCount').textContent='/ 0';shell.querySelector('[data-prev]').disabled=true;shell.querySelector('[data-next]').disabled=true;return;}
  select.disabled=false;input.disabled=false;page=Math.max(1,Math.min(Number(doc.pages)||1,Number(page)||1));input.value=page;input.max=doc.pages||1;document.querySelector('#sourceCount').textContent=`/ ${doc.pages||1}`;
  shell.querySelector('[data-prev]').disabled=page<=1;shell.querySelector('[data-next]').disabled=page>=(doc.pages||1);persist();
  stage.innerHTML='<p role="status">자료를 불러오는 중…</p>';request=new AbortController();
  try{const response=await fetch(`/api/p/${PID}/courses/${CID}/documents/${doc.id}/preview?page=${page}`,{headers:ACCESS?{'X-App-Code':ACCESS}:{},signal:request.signal});if(!response.ok)throw Error('원본을 불러오지 못했어.');const blob=await response.blob();if(turn!==epoch)return;url=URL.createObjectURL(blob);const img=new Image();img.alt=`${doc.name} ${page}페이지`;img.src=url;stage.replaceChildren(img);stage.scrollTop=0;}
  catch(e){if(turn!==epoch||e.name==='AbortError')return;stage.innerHTML='<p role="alert">자료를 불러오지 못했어.</p><button data-retry>다시 시도</button>';stage.querySelector('[data-retry]').onclick=showPage;}
 }
 select.onchange=()=>{doc=COURSE.documents.find(d=>String(d.id)===select.value);page=1;showPage();};input.onchange=()=>{page=input.value;showPage();};
 shell.querySelector('[data-prev]').onclick=()=>{if(doc){page--;showPage();}};shell.querySelector('[data-next]').onclick=()=>{if(doc){page++;showPage();}};
 shell.querySelector('[data-pen]').onclick=()=>{if(doc)openAnnotator(doc.id,doc.pages,doc.name,page);};
 const previousRender=window.render;
 window.render=function(){previousRender();const docs=COURSE?.documents||[],last=saved();select.replaceChildren(...docs.map(d=>{const o=document.createElement('option');o.value=d.id;o.textContent=d.name;return o;}));doc=docs.find(d=>d.id===last.document)||docs[0]||null;page=last.page||1;if(doc)select.value=doc.id;showPage();};
 const previousOpen=window.openCourse;
 window.openCourse=async function(id){++epoch;request?.abort();if(url){URL.revokeObjectURL(url);url=null;}stage.replaceChildren();doc=null;await previousOpen(id);if(CID!==id||!COURSE)return;drawer.close();const target=A?.overview?'sum':'dash';const tab=[...document.querySelectorAll('.tab')].find(t=>t.getAttribute('onclick')?.includes(`'${target}'`));pane(target,tab);};
 const previousSwitch=window.switchProfile;
 window.switchProfile=async function(){++epoch;request?.abort();if(url){URL.revokeObjectURL(url);url=null;}stage.replaceChildren();drawer.close();return previousSwitch();};
 document.querySelector('#studyMission').addEventListener('click',e=>{if(e.target.closest('[data-study-action="upload"]'))openMenu();},true);
})();
