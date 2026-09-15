"""Create an isolated responsive-layout fixture. Never connects to production APIs."""
from pathlib import Path
import json,zipfile,io
root=Path(__file__).resolve().parents[1]
profile={'id':1,'name':'레이아웃 테스트','is_owner':True,'has_pin':False}
course={'id':1,'name':'경제학원론','namespace':'fixture-only','days_left':14,'documents':[{'id':1,'name':'1주차 수요와 공급.pdf','pages':12,'type':'lecture','extraction':'text','images':0},{'id':2,'name':'강의 필기.png','pages':1,'type':'notes','extraction':'pending_vision','images':1}],'attempts':[],'due_count':3,'tutor_history':[],'exam_pattern':None,'analysis':{'overview':'수요와 공급을 이해하고 시장 균형의 변화를 복습해봐. 이 화면은 반응형 배치만 확인하는 독립 테스트 자료야.','course_profile':{'detected_subject':'경제학','study_style':'conceptual'},'study_plan':[{'label':'오늘','goal':'수요와 공급','tasks':['개념 확인','복습 카드','연습 문제']}],'must_understand':[{'text':'수요량의 변화와 수요의 변화는 어떻게 다를까?','source_type':'lecture','source_doc':'1주차 수요와 공급.pdf','page':3}], 'flashcards':[]}}
mock='''<script>const previewProfile=PROFILE,previewCourse=COURSE;
window.fetch=async function(url,options={}){let result={};if(url==='/api/profiles')result=[previewProfile];else if(url==='/api/session')result={logged_in:true,profile:previewProfile};else if(url==='/api/runtime')result={ai_configured:false};else if(url.endsWith('/courses'))result=[{id:1,name:previewCourse.name,analyzed:true,days_left:14}];else if(url.endsWith('/courses/1'))result=previewCourse;else if(url.endsWith('/due-cards'))result={due:[],all:[]};else if(url.endsWith('/tutor'))result={answer:'현재 과목의 자료로 설명하는 예시야. 1주차 수요와 공급.pdf p.3'};return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}});};
</script>'''.replace('PROFILE',json.dumps(profile,ensure_ascii=False)).replace('COURSE',json.dumps(course,ensure_ascii=False))
html=(root/'static/index.html').read_text().replace('<script>','<script>',1).replace('<body>',mock+'<body>',1)
for path in ['/app.css','/app.js','/detail.js','/icons/','/manifest.webmanifest']:html=html.replace(path,'/preview'+path)
html=html.replace('if("serviceWorker" in navigator)navigator.serviceWorker.register("/sw.js").catch(()=>{});','')
html=html.replace('</body>','<script>window.addEventListener("load",()=>setTimeout(()=>openCourse(1),100));</script></body>')
sizes=[('Android phone portrait',360,800),('Android phone landscape',800,360),('iPhone portrait',390,844),('iPhone landscape',844,390),('Android tablet landscape',1280,800),('iPad portrait',820,1180),('iPad landscape',1180,820),('iPad Pro landscape',1366,1024),('Desktop',1920,1080)]
buttons=''.join(f'<button onclick="document.querySelector(\'iframe\').style.width=\'{w}px\';document.querySelector(\'iframe\').style.height=\'{h}px\'">{label}</button>' for label,w,h in sizes)
qa='<!doctype html><html><meta charset="utf-8"><title>FOR EST layout QA</title><style>body{font:14px system-ui;margin:12px}nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}button{padding:12px}iframe{border:1px solid #888;display:block;width:1280px;height:800px}</style><nav>'+buttons+'</nav><iframe title="FOR EST isolated preview" src="/preview/index.html"></iframe></html>'
with zipfile.ZipFile(root.parent/'forest-layout-preview.zip','w',zipfile.ZIP_DEFLATED) as z:
 z.writestr('qa.html',qa);z.writestr('preview/index.html',html)
 for path in ['app.css','app.js','detail.js','manifest.webmanifest','icons/icon-192.png']:
  z.write(root/'static'/path,'preview/'+path)
print('Preview uses synthetic records only; no user data or real API requests.')
