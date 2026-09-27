/* Study-first shell. Existing controls and private API authorization are preserved. */
(()=>{
 const ws=document.querySelector('#ws'),side=document.querySelector('.side'),management=ws.firstElementChild;
 const visibility=document.createElement('style');visibility.textContent='#ws.hidden{display:none!important}';document.head.append(visibility);
 const header=management.firstElementChild;
 const drawer=document.createElement('dialog');drawer.id='studyDrawer';drawer.setAttribute('aria-label','과목과 자료 관리');
 drawer.innerHTML='<div class="drawer-head"><h2>과목 · 자료 관리</h2><button type="button" data-close-drawer aria-label="메뉴 닫기">닫기 ×</button></div>';
 document.body.append(drawer);drawer.append(side,management);
 drawer.querySelector('[data-close-drawer]').onclick=()=>drawer.close();
 const top=document.querySelector('#app .top'),menu=document.createElement('button');menu.type='button';menu.textContent='☰';menu.setAttribute('aria-label','과목과 자료 메뉴');menu.setAttribute('aria-haspopup','dialog');menu.setAttribute('aria-controls','studyDrawer');menu.setAttribute('aria-expanded','false');top.prepend(menu);
 function openMenu(){drawer.showModal();menu.setAttribute('aria-expanded','true');}menu.onclick=openMenu;
 drawer.addEventListener('click',event=>{if(event.target===drawer)drawer.close();});
 drawer.addEventListener('close',()=>menu.setAttribute('aria-expanded','false'));
 const shell=document.createElement('div');shell.className='study-split';
 shell.innerHTML='<section class="study-source" aria-label="원본 자료"><div class="source-tools"><select id="sourceDocument" aria-label="자료 선택"></select><div class="source-pages"><label for="sourcePage">페이지</label><input id="sourcePage" type="number" min="1" inputmode="numeric" aria-label="이동할 페이지"><span id="sourceCount"></span><button data-pen>현재 페이지 필기</button></div></div><div id="sourceStage" tabindex="0" aria-label="자료 페이지를 세로로 스크롤"></div></section><div class="study-divider"><input type="range" min="30" max="65" value="45" aria-label="자료 영역 너비"></div><section class="study-explanation" aria-label="설명과 학습"></section>';
 const right=shell.querySelector('.study-explanation');
 [...ws.children].forEach(el=>right.append(el));ws.append(header,shell);header.classList.add('study-course-header');
 const mobile=document.createElement('div');mobile.className='study-mobile-tabs';mobile.innerHTML='<button data-view="source">자료</button><button data-view="explanation">설명 · 학습</button>';header.after(mobile);
 mobile.onclick=e=>{const b=e.target.closest('[data-view]');if(b){shell.dataset.view=b.dataset.view;mobile.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));if(b.dataset.view==='source')requestAnimationFrame(()=>scrollToPage(page));}};
 shell.dataset.view='explanation';mobile.querySelector('[data-view="explanation"]').setAttribute('aria-pressed','true');
 const divider=shell.querySelector('input[type=range]'),widthKey='forest_source_width';
 try{const savedWidth=Math.max(30,Math.min(65,Number(localStorage.getItem(widthKey))||45));divider.value=savedWidth;shell.style.setProperty('--source-width',savedWidth+'%');}catch{}
 divider.oninput=e=>{const width=e.target.value;shell.style.setProperty('--source-width',width+'%');try{localStorage.setItem(widthKey,width);}catch{}};
 let doc=null,page=1,epoch=0,observer=null,previews=new Map(),scrollFrame=0,restoreTarget=0,restoreActive=false;
 const select=document.querySelector('#sourceDocument'),input=document.querySelector('#sourcePage'),stage=document.querySelector('#sourceStage');
 const key=()=>`forest_reading_${PID}_${CID}`;
 function saved(){try{return JSON.parse(localStorage.getItem(key())||'{}');}catch{return {};}}
 function persist(){if(doc)try{localStorage.setItem(key(),JSON.stringify({document:doc.id,page}));}catch{}}
 function clearPages(){++epoch;observer?.disconnect();observer=null;cancelAnimationFrame(scrollFrame);scrollFrame=0;restoreTarget=0;restoreActive=false;for(const state of previews.values()){state.controller?.abort();if(state.url)URL.revokeObjectURL(state.url);}previews.clear();stage.replaceChildren();}
 function scrollToPage(number){const section=stage.querySelector(`[data-source-page="${number}"]`);if(section)stage.scrollTop=section.offsetTop;}
 function markSourcePage(number){stage.querySelector('[aria-current="page"]')?.removeAttribute('aria-current');stage.querySelector(`[data-source-page="${number}"]`)?.setAttribute('aria-current','page');}
 function restorePagePosition(){if(!restoreActive||!restoreTarget)return;scrollToPage(restoreTarget);markSourcePage(restoreTarget);}
 function releasePageRestore(){restoreActive=false;restoreTarget=0;visiblePage();}
 function sourcePageAt(scrollTop,viewHeight,scrollHeight,pageTops){if(scrollHeight>viewHeight+2&&scrollTop+viewHeight>=scrollHeight-2)return pageTops.length;const marker=scrollTop+viewHeight*.25;let current=1;for(let i=0;i<pageTops.length;i++){if(pageTops[i]<=marker)current=i+1;else break;}return current;}
 function visiblePage(){if(restoreActive||!doc||!stage.clientHeight)return;const tops=[...stage.querySelectorAll('[data-source-page]')].map(section=>section.offsetTop),current=sourcePageAt(stage.scrollTop,stage.clientHeight,stage.scrollHeight,tops);markSourcePage(current);if(current!==page){page=current;if(document.activeElement!==input)input.value=page;persist();}}
 async function loadPreview(section){const number=Number(section.dataset.sourcePage),state=previews.get(number),turn=epoch;if(!state||state.controller||state.url||state.loading)return;state.loading=true;state.controller=new AbortController();const controller=state.controller;state.preview.textContent='페이지를 불러오는 중…';
  try{const response=await fetch(`/api/p/${PID}/courses/${CID}/documents/${doc.id}/preview?page=${number}`,{headers:ACCESS?{'X-App-Code':ACCESS}:{},signal:controller.signal});if(!response.ok)throw Error('원본을 불러오지 못했어.');const blob=await response.blob();if(turn!==epoch||controller.signal.aborted)return;state.url=URL.createObjectURL(blob);const img=new Image();img.alt=`${doc.name} ${number}페이지`;img.onload=()=>{if(turn===epoch){state.preview.style.minHeight='';if(restoreActive&&number<=restoreTarget)requestAnimationFrame(restorePagePosition);visiblePage();}};img.onerror=()=>{if(turn===epoch&&state.url){URL.revokeObjectURL(state.url);state.url=null;showPreviewError(section);}};state.preview.replaceChildren(img);img.src=state.url;}
  catch(e){if(turn===epoch&&e.name!=='AbortError')showPreviewError(section);}finally{if(state.controller===controller)state.controller=null;state.loading=false;}
 }
 function showPreviewError(section){const state=previews.get(Number(section.dataset.sourcePage));if(!state)return;state.preview.innerHTML='<p role="alert">이 페이지를 불러오지 못했어.</p><button type="button" data-retry>다시 시도</button>';state.preview.querySelector('[data-retry]').onclick=()=>loadPreview(section);}
 function showDocument(){
  clearPages();
  shell.querySelector('[data-pen]').disabled=!doc;
  if(!doc){stage.innerHTML='<div class="source-empty"><h2>첫 자료를 추가해</h2><p>PDF나 사진을 올리면 여기에서 설명과 함께 볼 수 있어.</p><button data-add>자료 추가하기</button></div>';stage.querySelector('[data-add]').onclick=openMenu;select.disabled=true;input.disabled=true;input.value='';document.querySelector('#sourceCount').textContent='/ 0';return;}
  select.disabled=false;input.disabled=false;page=Math.max(1,Math.min(Number(doc.pages)||1,Number(page)||1));input.value=page;input.max=doc.pages||1;document.querySelector('#sourceCount').textContent=`/ ${doc.pages||1}`;
  persist();stage.innerHTML=Array.from({length:Number(doc.pages)||1},(_,i)=>`<section class="source-page" data-source-page="${i+1}" aria-label="${i+1}페이지"><div class="source-page-heading">${i+1} / ${doc.pages||1}페이지</div><div class="source-preview" role="status">페이지를 불러오는 중…</div></section>`).join('');
  for(const section of stage.children)previews.set(Number(section.dataset.sourcePage),{preview:section.querySelector('.source-preview'),controller:null,url:null,loading:false});
  observer=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting)loadPreview(entry.target);else{const state=previews.get(Number(entry.target.dataset.sourcePage));if(state?.url){const img=state.preview.querySelector('img');if(img)img.onload=img.onerror=null;state.preview.style.minHeight=`${state.preview.offsetHeight}px`;state.preview.textContent='스크롤하면 페이지를 불러와';URL.revokeObjectURL(state.url);state.url=null;}}}},{root:stage,rootMargin:'400px 0px'});
  for(const section of stage.children)observer.observe(section);
  restoreTarget=page;restoreActive=true;stage.scrollTop=0;markSourcePage(page);const turn=epoch;requestAnimationFrame(()=>{if(turn===epoch)restorePagePosition();});
 }
 stage.addEventListener('pointerdown',releasePageRestore,{passive:true});stage.addEventListener('wheel',releasePageRestore,{passive:true});stage.addEventListener('keydown',releasePageRestore);
 stage.addEventListener('scroll',()=>{if(!restoreActive&&!scrollFrame)scrollFrame=requestAnimationFrame(()=>{scrollFrame=0;visiblePage();});},{passive:true});
 select.onchange=()=>{doc=COURSE.documents.find(d=>String(d.id)===select.value);page=1;showDocument();};input.onchange=()=>{if(doc){page=Math.max(1,Math.min(Number(doc.pages)||1,Math.round(Number(input.value)||page)));input.value=page;persist();restoreTarget=page;restoreActive=true;restorePagePosition();}};
 shell.querySelector('[data-pen]').onclick=()=>{if(doc)openAnnotator(doc.id,doc.pages,doc.name,page);};
 const previousRender=window.render;
 window.render=function(){previousRender();const docs=COURSE?.documents||[],last=saved();select.replaceChildren(...docs.map(d=>{const o=document.createElement('option');o.value=d.id;o.textContent=d.name;return o;}));doc=docs.find(d=>d.id===last.document)||docs[0]||null;page=last.page||1;if(doc)select.value=doc.id;showDocument();};
 const previousOpen=window.openCourse;
 window.openCourse=async function(id){clearPages();doc=null;await previousOpen(id);if(CID!==id||!COURSE)return;drawer.close();const target=A?.overview?'sum':'dash';const tab=[...document.querySelectorAll('.tab')].find(t=>t.getAttribute('onclick')?.includes(`'${target}'`));pane(target,tab);};
 const previousSwitch=window.switchProfile;
 window.switchProfile=async function(){clearPages();doc=null;drawer.close();return previousSwitch();};
 document.querySelector('#studyMission').addEventListener('click',e=>{if(e.target.closest('[data-study-action="upload"]'))openMenu();},true);
})();
