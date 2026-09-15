(()=>{
  const APP_NAME="FOR'EST";
  const isStandalone=()=>window.matchMedia("(display-mode: standalone)").matches||window.navigator.standalone===true;
  const isiOS=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
  let installPrompt=null;

  const style=document.createElement("style");
  style.textContent=`
    .forest-install{position:fixed;right:max(16px,env(safe-area-inset-right));bottom:max(16px,env(safe-area-inset-bottom));z-index:9998;border:0;border-radius:999px;padding:12px 17px;background:#d6ff00;color:#17231e;box-shadow:0 10px 28px rgba(23,35,30,.24);font-weight:900;min-height:48px}
    .forest-install-sheet{position:fixed;inset:0;z-index:9999;display:grid;place-items:end center;padding:max(14px,env(safe-area-inset-top)) max(14px,env(safe-area-inset-right)) max(14px,env(safe-area-inset-bottom)) max(14px,env(safe-area-inset-left));background:rgba(15,23,42,.42)}
    .forest-install-card{width:min(100%,520px);background:#fff;border-radius:24px;padding:22px;color:#17231e;box-shadow:0 24px 70px rgba(15,23,42,.28)}
    .forest-install-card h2{margin:0 0 10px}.forest-install-card ol{padding-left:22px;line-height:1.75}.forest-install-card .install-actions{display:flex;gap:8px}.forest-install-card button{flex:1}
    @media(max-height:500px) and (orientation:landscape){.forest-install-card{max-height:92dvh;overflow:auto}}
  `;
  document.head.appendChild(style);

  function closeSheet(){document.querySelector(".forest-install-sheet")?.remove()}
  function showGuide(){
    closeSheet();
    const sheet=document.createElement("div");
    sheet.className="forest-install-sheet";
    sheet.setAttribute("role","dialog");sheet.setAttribute("aria-modal","true");sheet.setAttribute("aria-label",APP_NAME+" 설치 안내");
    const steps=isiOS
      ? "<li>Safari 아래쪽 <b>공유</b> 버튼을 눌러.</li><li><b>홈 화면에 추가</b>를 선택해.</li><li>이름이 <b>FOR'EST</b>인지 확인하고 <b>추가</b>를 눌러.</li>"
      : "<li>브라우저 메뉴를 열어.</li><li><b>앱 설치</b> 또는 <b>홈 화면에 추가</b>를 눌러.</li><li><b>FOR'EST</b> 설치를 확인해.</li>";
    sheet.innerHTML=`<div class="forest-install-card"><h2>FOR'EST 설치</h2><p>앱처럼 전체 화면으로 바로 실행할 수 있어.</p><ol>${steps}</ol><div class="install-actions"><button class="ghost" data-close>닫기</button></div></div>`;
    sheet.addEventListener("click",e=>{if(e.target===sheet||e.target.closest("[data-close]"))closeSheet()});
    document.body.appendChild(sheet);
  }
  async function install(){
    if(installPrompt){
      installPrompt.prompt();
      await installPrompt.userChoice;
      installPrompt=null;
      render();
      return;
    }
    showGuide();
  }
  function render(){
    document.querySelector(".forest-install")?.remove();
    if(isStandalone())return;
    const button=document.createElement("button");
    button.type="button";button.className="forest-install";button.textContent="앱으로 설치";
    button.setAttribute("aria-label",APP_NAME+" 홈 화면에 설치");
    button.addEventListener("click",install);
    document.body.appendChild(button);
  }

  addEventListener("beforeinstallprompt",e=>{e.preventDefault();installPrompt=e;render()});
  addEventListener("appinstalled",()=>{installPrompt=null;render()});
  addEventListener("DOMContentLoaded",render,{once:true});
  addEventListener("pageshow",render);
})();