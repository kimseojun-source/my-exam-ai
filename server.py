
import os, json, re, sqlite3, tempfile, math, hashlib, base64
from pathlib import Path
from datetime import date, datetime, timedelta
from collections import Counter
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader

BASE=Path(__file__).parent
DATA=BASE/"data"
DATA.mkdir(exist_ok=True)
DB=DATA/"exam_ai.db"
app=FastAPI(title="My Exam AI Complete",version="5.0")

def nowiso(): return datetime.now().isoformat(timespec="seconds")

# ---------- optional account-level access code ----------
@app.middleware("http")
async def access_guard(request:Request,call_next):
    required=os.getenv("APP_ACCESS_CODE","").strip()
    if required and request.url.path.startswith("/api/"):
        if request.headers.get("x-app-code","") != required:
            return JSONResponse({"detail":"앱 접속코드가 필요해."},status_code=401)
    return await call_next(request)

# ---------- database ----------
def db():
    con=sqlite3.connect(DB)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS profiles(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      is_owner INTEGER NOT NULL DEFAULT 0,
      pin_hash TEXT DEFAULT '',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS courses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      profile_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      exam_date TEXT,
      created_at TEXT NOT NULL,
      profile_json TEXT DEFAULT '{}',
      analysis_json TEXT DEFAULT '{}',
      FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS documents(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      name TEXT NOT NULL,
      sha256 TEXT NOT NULL,
      pages INTEGER NOT NULL,
      text_json TEXT NOT NULL,
      document_type TEXT NOT NULL DEFAULT 'lecture',
      raw_path TEXT DEFAULT '',
      extraction_mode TEXT DEFAULT 'text',
      image_count INTEGER DEFAULT 0,
      created_at TEXT DEFAULT '',
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS attempts(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      score REAL NOT NULL,
      detail_json TEXT NOT NULL,
      mode TEXT DEFAULT 'adaptive',
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS card_reviews(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      card_key TEXT NOT NULL,
      rating INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS tutor_messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS exam_patterns(
      course_id INTEGER PRIMARY KEY,
      analysis_json TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)
    # migrations for older builds
    for table, col, decl in [
        ("documents","document_type","TEXT NOT NULL DEFAULT 'lecture'"),
        ("documents","raw_path","TEXT DEFAULT ''"),
        ("documents","extraction_mode","TEXT DEFAULT 'text'"),
        ("documents","image_count","INTEGER DEFAULT 0"),
        ("documents","created_at","TEXT DEFAULT ''"),
        ("attempts","mode","TEXT DEFAULT 'adaptive'")
    ]:
        cols=[r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
        if col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    if not con.execute("SELECT 1 FROM profiles LIMIT 1").fetchone():
        con.execute("INSERT INTO profiles(name,is_owner,created_at) VALUES(?,?,?)",("내 프로필",1,nowiso()))
    con.commit()
    return con

def hash_pin(pin):
    return "" if not pin else hashlib.sha256(("my-exam-ai-v5:"+pin).encode()).hexdigest()

def profile_row(pid):
    con=db();r=con.execute("SELECT * FROM profiles WHERE id=?",(pid,)).fetchone();con.close()
    if not r: raise HTTPException(404,"사용자 프로필을 찾지 못했어.")
    return dict(r)

def course_row(pid,cid):
    con=db();r=con.execute("SELECT * FROM courses WHERE id=? AND profile_id=?",(cid,pid)).fetchone();con.close()
    if not r: raise HTTPException(404,"이 사용자 공간에 해당 과목이 없어.")
    return dict(r)

def days_left(s):
    if not s:return None
    try:return (date.fromisoformat(s)-date.today()).days
    except:return None

# ---------- OpenAI ----------
def client():
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:return None
    from openai import OpenAI
    return OpenAI(api_key=key)

def model_name(): return os.getenv("OPENAI_MODEL","gpt-5.6")
def vision_model(): return os.getenv("OPENAI_VISION_MODEL",model_name())

def json_call(prompt,schema,web=False):
    c=client()
    if not c:return None
    kw={"model":model_name(),"input":prompt,
        "text":{"format":{"type":"json_schema","name":"result","strict":True,"schema":schema}}}
    if web: kw["tools"]=[{"type":"web_search"}]
    r=c.responses.create(**kw)
    return json.loads(r.output_text)

def text_call(prompt,web=False):
    c=client()
    if not c:return None
    kw={"model":model_name(),"input":prompt}
    if web:kw["tools"]=[{"type":"web_search"}]
    return c.responses.create(**kw).output_text

# ---------- PDF / visual understanding ----------
def inspect_pdf(path):
    total=0;images=0
    try:
        import fitz
        d=fitz.open(path);total=len(d)
        for p in d:
            images += len(p.get_images(full=True))
        d.close()
    except Exception:
        try: total=len(PdfReader(path).pages)
        except: pass
    return total,images

def extract_pdf(path):
    reader=PdfReader(path);pages=[];nonempty=0
    for i,p in enumerate(reader.pages,1):
        try:t=(p.extract_text() or "").strip()
        except:t=""
        if len(t)>=30:nonempty+=1
        if t:pages.append({"page":i,"text":t})
    coverage=nonempty/max(1,len(reader.pages))
    return pages,len(reader.pages),coverage

VISUAL_SCHEMA={"type":"object","properties":{
  "pages":{"type":"array","items":{"type":"object","properties":{
    "page":{"type":"integer"},"text":{"type":"string"}
  },"required":["page","text"],"additionalProperties":False}}
},"required":["pages"],"additionalProperties":False}

def visual_pdf_notes(path,filename):
    c=client()
    if not c:return []
    uploaded=None
    try:
        with open(path,"rb") as f:
            uploaded=c.files.create(file=f,purpose="user_data")
        prompt="""이 PDF를 대학 시험 공부용으로 시각적으로 읽어라.
스캔된 글자, 표, 그래프, 도식, 수식, 이미지 속 핵심 라벨을 읽어서 페이지별 학습 텍스트로 바꿔라.
이미 일반 텍스트로 읽힐 법한 문장을 장황하게 반복하지 말고, 텍스트 추출이 놓치기 쉬운 시각 정보에 집중한다.
페이지 번호는 PDF 실제 페이지 순서 기준으로 기록한다.
보이지 않는 내용은 추측하지 않는다."""
        r=c.responses.create(
            model=vision_model(),
            input=[{"role":"user","content":[
              {"type":"input_file","file_id":uploaded.id},
              {"type":"input_text","text":prompt}
            ]}],
            text={"format":{"type":"json_schema","name":"pdf_visual","strict":True,"schema":VISUAL_SCHEMA}}
        )
        return json.loads(r.output_text).get("pages",[])
    except Exception as e:
        print("visual PDF failed",repr(e));return []
    finally:
        if uploaded:
            try:c.files.delete(uploaded.id)
            except:pass

def merge_visual(text_pages,visual_pages):
    m={int(x["page"]):x["text"] for x in text_pages}
    for v in visual_pages:
        p=int(v.get("page",0));t=(v.get("text") or "").strip()
        if p>0 and t:
            m[p]=(m.get(p,"")+"\n\n[시각자료/스캔 보강]\n"+t).strip()
    return [{"page":p,"text":m[p]} for p in sorted(m)]

def safe_name(s):
    return re.sub(r"[^0-9A-Za-z가-힣._-]+","_",s)[:120]

# ---------- scoped documents ----------
def course_docs(pid,cid,types=None):
    course_row(pid,cid)
    con=db()
    q="""SELECT d.* FROM documents d JOIN courses c ON c.id=d.course_id
         WHERE d.course_id=? AND c.profile_id=?"""
    args=[cid,pid]
    if types:
        q+=f" AND d.document_type IN ({','.join('?'*len(types))})";args+=list(types)
    q+=" ORDER BY d.id"
    rows=con.execute(q,args).fetchall();con.close()
    return [{"id":r["id"],"name":r["name"],"pages":json.loads(r["text_json"]),
             "document_type":r["document_type"],"raw_path":r["raw_path"],
             "extraction_mode":r["extraction_mode"],"image_count":r["image_count"]} for r in rows]

def chunks_from_docs(docs,max_chars=1800):
    out=[]
    for d in docs:
        for p in d["pages"]:
            text=re.sub(r"\s+"," ",p["text"]).strip()
            for start in range(0,len(text),max_chars-250):
                part=text[start:start+max_chars]
                if len(part)>80:
                    out.append({"doc":d["name"],"page":p["page"],"text":part,"type":d["document_type"]})
    return out

STOP=set("그리고 그러나 또는 대한 하는 있는 없는 으로 에서 에게 이것 저것 해당 관련 통해 경우 위해 따른 보다 매우 또한 내용 자료 강의".split())
def tokenize(s):return [x for x in re.findall(r"[가-힣A-Za-z0-9]{2,}",s.lower()) if x not in STOP]
def retrieve(chunks,q,k=18):
    qc=Counter(tokenize(q));scored=[]
    if not qc:return chunks[:k]
    for c in chunks:
        tc=Counter(tokenize(c["text"]))
        score=sum((1+math.log(tc[t]))*(1+math.log(qc[t])) for t in qc if tc[t])
        if score:scored.append((score,c))
    scored.sort(key=lambda x:x[0],reverse=True)
    return [x for _,x in scored[:k]] or chunks[:k]

# ---------- schemas ----------
item_schema={"type":"object","properties":{
 "text":{"type":"string"},"source_doc":{"type":"string"},"page":{"type":["integer","null"]},
 "source_type":{"type":"string","enum":["lecture","integrated","external"]}
},"required":["text","source_doc","page","source_type"],"additionalProperties":False}

ANALYSIS_SCHEMA={"type":"object","properties":{
 "course_profile":{"type":"object","properties":{
   "detected_subject":{"type":"string"},"field":{"type":"string"},
   "study_style":{"type":"string","enum":["memorization","conceptual","calculation","case","mixed"]},
   "freshness_needed":{"type":"boolean"},"reason":{"type":"string"}
 },"required":["detected_subject","field","study_style","freshness_needed","reason"],"additionalProperties":False},
 "overview":{"type":"string"},
 "must_memorize":{"type":"array","items":item_schema},
 "must_understand":{"type":"array","items":item_schema},
 "exam_hotspots":{"type":"array","items":item_schema},
 "confusing_pairs":{"type":"array","items":item_schema},
 "formula_or_frameworks":{"type":"array","items":item_schema},
 "external_knowledge":{"type":"array","items":{"type":"object","properties":{
   "title":{"type":"string"},"text":{"type":"string"},"why":{"type":"string"},
   "source_type":{"type":"string","enum":["model_knowledge","web"]}
 },"required":["title","text","why","source_type"],"additionalProperties":False}},
 "flashcards":{"type":"array","items":{"type":"object","properties":{
   "front":{"type":"string"},"back":{"type":"string"},"source_doc":{"type":"string"},"page":{"type":["integer","null"]}
 },"required":["front","back","source_doc","page"],"additionalProperties":False}},
 "study_plan":{"type":"array","items":{"type":"object","properties":{
   "label":{"type":"string"},"goal":{"type":"string"},"tasks":{"type":"array","items":{"type":"string"}}
 },"required":["label","goal","tasks"],"additionalProperties":False}}
},"required":["course_profile","overview","must_memorize","must_understand","exam_hotspots","confusing_pairs","formula_or_frameworks","external_knowledge","flashcards","study_plan"],"additionalProperties":False}

QUESTION_SCHEMA={"type":"object","properties":{"questions":{"type":"array","items":{"type":"object","properties":{
 "type":{"type":"string","enum":["mcq","true_false","short"]},"question":{"type":"string"},
 "choices":{"type":"array","items":{"type":"string"}},"answer":{"type":"string"},"explanation":{"type":"string"},
 "tags":{"type":"array","items":{"type":"string"}},"source_doc":{"type":"string"},"page":{"type":["integer","null"]},
 "source_type":{"type":"string","enum":["lecture","integrated"]},"difficulty":{"type":"string","enum":["easy","medium","hard"]}
},"required":["type","question","choices","answer","explanation","tags","source_doc","page","source_type","difficulty"],"additionalProperties":False}}},"required":["questions"],"additionalProperties":False}

GRADE_SCHEMA={"type":"object","properties":{
 "correct":{"type":"boolean"},"score":{"type":"integer","minimum":0,"maximum":100},
 "feedback":{"type":"string"},"ideal_answer":{"type":"string"}
},"required":["correct","score","feedback","ideal_answer"],"additionalProperties":False}

PATTERN_SCHEMA={"type":"object","properties":{
 "evidence_count":{"type":"integer"},
 "question_formats":{"type":"array","items":{"type":"string"}},
 "recurring_topics":{"type":"array","items":{"type":"object","properties":{
   "topic":{"type":"string"},"evidence":{"type":"string"},"frequency":{"type":"string"}
 },"required":["topic","evidence","frequency"],"additionalProperties":False}},
 "difficulty_profile":{"type":"string"},
 "trap_patterns":{"type":"array","items":{"type":"string"}},
 "answer_style":{"type":"string"},
 "evidence_based_focus":{"type":"array","items":{"type":"string"}},
 "warning":{"type":"string"}
},"required":["evidence_count","question_formats","recurring_topics","difficulty_profile","trap_patterns","answer_style","evidence_based_focus","warning"],"additionalProperties":False}

def fallback_analysis(name,chunks):
    vals=[];seen=set()
    for c in chunks:
        for s in re.split(r"(?<=[.!?。])\s+|[\n•·]+",c["text"]):
            s=s.strip()
            if 30<=len(s)<=220 and s[:70] not in seen:
                seen.add(s[:70]);vals.append({"text":s,"source_doc":c["doc"],"page":c["page"],"source_type":"lecture"})
    vals=vals[:45]
    return {"course_profile":{"detected_subject":name,"field":"자동","study_style":"mixed","freshness_needed":False,"reason":"API 미연결 기본 분석"},
      "overview":"강의자료 기반 기본 분석이야.","must_memorize":vals[:8],"must_understand":vals[8:16],
      "exam_hotspots":vals[16:24],"confusing_pairs":vals[24:30],"formula_or_frameworks":vals[30:36],
      "external_knowledge":[],"flashcards":[{"front":v["text"][:70]+"…의 핵심은?","back":v["text"],"source_doc":v["source_doc"],"page":v["page"]} for v in vals[:15]],
      "study_plan":[{"label":"1단계","goal":"범위 파악","tasks":["핵심 확인"]},{"label":"2단계","goal":"회상","tasks":["플래시카드","문제"]},{"label":"3단계","goal":"약점","tasks":["오답 복습"]}]}

# ---------- spaced repetition ----------
def due_info(cid,flashcards):
    con=db();rows=con.execute("SELECT card_key,rating,created_at FROM card_reviews WHERE course_id=? ORDER BY id",(cid,)).fetchall();con.close()
    hist={}
    for r in rows:hist.setdefault(r["card_key"],[]).append((r["rating"],datetime.fromisoformat(r["created_at"])))
    now=datetime.now();out=[]
    for card in flashcards:
        key=card["front"];h=hist.get(key,[])
        if not h:
            due=now;interval=0
        else:
            rating,last=h[-1];good=sum(1 for x,_ in h[-5:] if x>=3)
            if rating<=1:interval=0
            elif rating==2:interval=1
            elif rating==3:interval=min(30,3*(2**max(0,good-1)))
            else:interval=min(60,7*(2**max(0,good-1)))
            due=last+timedelta(days=interval)
        out.append({"card":card,"due":due.isoformat(timespec="minutes"),"is_due":due<=now,"interval_days":interval})
    return out

def weakness_context(pid,cid):
    course_row(pid,cid);con=db()
    rows=con.execute("""SELECT a.detail_json FROM attempts a JOIN courses c ON c.id=a.course_id
                        WHERE a.course_id=? AND c.profile_id=? ORDER BY a.id DESC LIMIT 5""",(cid,pid)).fetchall();con.close()
    tags=Counter()
    for r in rows:
        try:
            for w in json.loads(r["detail_json"]).get("wrong",[]):
                for t in w.get("tags",[]):tags[t]+=1
        except:pass
    return [t for t,_ in tags.most_common(6)]

# ---------- profiles ----------
@app.get("/api/profiles")
def list_profiles():
    con=db();rows=con.execute("SELECT * FROM profiles ORDER BY is_owner DESC,id").fetchall();con.close()
    return [{"id":r["id"],"name":r["name"],"is_owner":bool(r["is_owner"]),"has_pin":bool(r["pin_hash"])} for r in rows]

@app.post("/api/profiles")
def add_profile(name:str=Form(...),pin:str=Form("")):
    con=db();n=con.execute("SELECT COUNT(*) n FROM profiles").fetchone()["n"]
    if n>=2:con.close();raise HTTPException(400,"이 버전은 한 계정에서 사용자 2명까지 쓰도록 설정했어.")
    cur=con.execute("INSERT INTO profiles(name,is_owner,pin_hash,created_at) VALUES(?,?,?,?)",(name.strip() or "사용자 2",0,hash_pin(pin),nowiso()))
    con.commit();pid=cur.lastrowid;con.close();return {"id":pid}

@app.post("/api/profiles/{pid}/verify")
def verify(pid:int,pin:str=Form("")):
    p=profile_row(pid)
    if p["pin_hash"] and hash_pin(pin)!=p["pin_hash"]:raise HTTPException(403,"PIN이 맞지 않아.")
    return {"ok":True,"profile":{"id":p["id"],"name":p["name"],"is_owner":bool(p["is_owner"])}}

# ---------- courses ----------
@app.get("/api/p/{pid}/courses")
def list_courses(pid:int):
    profile_row(pid);con=db();rows=con.execute("SELECT * FROM courses WHERE profile_id=? ORDER BY id DESC",(pid,)).fetchall();con.close()
    return [{"id":r["id"],"name":r["name"],"exam_date":r["exam_date"],"analyzed":bool(json.loads(r["analysis_json"] or "{}")),"days_left":days_left(r["exam_date"])} for r in rows]

@app.post("/api/p/{pid}/courses")
def create_course(pid:int,name:str=Form("새 과목"),exam_date:str=Form("")):
    profile_row(pid);con=db();cur=con.execute("INSERT INTO courses(profile_id,name,exam_date,created_at) VALUES(?,?,?,?)",(pid,name.strip() or "새 과목",exam_date or None,nowiso()));con.commit();cid=cur.lastrowid;con.close();return {"id":cid}

@app.get("/api/p/{pid}/courses/{cid}")
def get_course(pid:int,cid:int):
    c=course_row(pid,cid);docs=course_docs(pid,cid);a=json.loads(c["analysis_json"] or "{}")
    con=db()
    attempts=con.execute("SELECT created_at,score,detail_json,mode FROM attempts WHERE course_id=? ORDER BY id DESC LIMIT 8",(cid,)).fetchall()
    msgs=con.execute("SELECT role,content,created_at FROM tutor_messages WHERE course_id=? ORDER BY id DESC LIMIT 12",(cid,)).fetchall()
    pattern=con.execute("SELECT analysis_json,updated_at FROM exam_patterns WHERE course_id=?",(cid,)).fetchone()
    con.close()
    due=due_info(cid,a.get("flashcards",[])) if a else []
    return {"id":cid,"name":c["name"],"exam_date":c["exam_date"],"days_left":days_left(c["exam_date"]),
      "namespace":f"profile:{pid}/course:{cid}",
      "documents":[{"name":d["name"],"pages":len(d["pages"]),"type":d["document_type"],"extraction":d["extraction_mode"],"images":d["image_count"]} for d in docs],
      "analysis":a,"due_count":sum(1 for x in due if x["is_due"]),
      "attempts":[{"created_at":x["created_at"],"score":x["score"],"mode":x["mode"],"detail":json.loads(x["detail_json"])} for x in attempts],
      "tutor_history":[dict(x) for x in reversed(msgs)],
      "exam_pattern":json.loads(pattern["analysis_json"]) if pattern else None}

@app.post("/api/p/{pid}/courses/{cid}/documents")
async def upload_docs(pid:int,cid:int,files:list[UploadFile]=File(...),document_type:str=Form("lecture")):
    course_row(pid,cid)
    allowed={"lecture","textbook","notes","past_exam"}
    if document_type not in allowed:document_type="lecture"
    folder=DATA/f"p{pid}"/f"c{cid}";folder.mkdir(parents=True,exist_ok=True)
    con=db();added=[]
    try:
        for f in files[:15]:
            if not f.filename.lower().endswith(".pdf"):continue
            raw=await f.read()
            if len(raw)>40*1024*1024:raise HTTPException(400,f"{f.filename}: 40MB 초과")
            sha=hashlib.sha256(raw).hexdigest()
            if con.execute("SELECT 1 FROM documents WHERE course_id=? AND sha256=?",(cid,sha)).fetchone():continue
            path=folder/f"{sha[:12]}_{safe_name(f.filename)}";path.write_bytes(raw)
            text_pages,total,coverage=extract_pdf(path)
            _,image_count=inspect_pdf(path)
            visual=[]
            extraction="text"
            # Automatic visual/OCR boost only when normal extraction is clearly insufficient
            # or the PDF is heavily visual. Can be disabled by AUTO_VISUAL_PDF=0.
            auto=os.getenv("AUTO_VISUAL_PDF","1")!="0"
            if auto and client() and (coverage<0.45 or image_count>=8):
                visual=visual_pdf_notes(path,f.filename)
                if visual:
                    text_pages=merge_visual(text_pages,visual)
                    extraction="text+vision" if coverage>=0.2 else "vision/OCR"
            if not text_pages:
                raise HTTPException(400,f"{f.filename}: 텍스트/시각 분석에 실패했어.")
            con.execute("""INSERT INTO documents(course_id,name,sha256,pages,text_json,document_type,raw_path,extraction_mode,image_count,created_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",(cid,f.filename,sha,total,json.dumps(text_pages,ensure_ascii=False),document_type,str(path),extraction,image_count,nowiso()))
            added.append({"name":f.filename,"pages":total,"type":document_type,"extraction":extraction,"images":image_count})
        con.commit()
    finally:con.close()
    if not added:raise HTTPException(400,"새로 추가된 PDF가 없어.")
    return {"added":added}

@app.post("/api/p/{pid}/courses/{cid}/analyze")
def analyze(pid:int,cid:int):
    c=course_row(pid,cid)
    docs=course_docs(pid,cid,["lecture","textbook","notes"])
    if not docs:docs=course_docs(pid,cid)
    if not docs:raise HTTPException(400,"먼저 강의자료를 넣어줘.")
    chunks=chunks_from_docs(docs)
    material="\n\n".join(f"[{x['doc']} p.{x['page']}]\n{x['text']}" for x in chunks[:140])
    prompt=f"""현재 네임스페이스 profile:{pid}/course:{cid}, 과목 '{c['name']}'만 분석한다.
다른 과목/사용자 자료는 존재하지 않는 것으로 취급한다.
시험 답안의 1차 기준은 현재 강의자료다. 외부지식은 external_knowledge로만 분리한다.
PDF 시각 보강 텍스트([시각자료/스캔 보강])도 강의자료의 해당 페이지 정보로 취급한다.
과목을 암기/개념/계산/사례/혼합형으로 판별하고 점수에 직접 도움 되는 순서로 구조화한다.
출제의도나 교수 성향은 기출 증거 없이 지어내지 않는다.
시험까지 남은 일수: {days_left(c['exam_date']) if c['exam_date'] else '미설정'}

자료:
{material[:260000]}"""
    a=json_call(prompt,ANALYSIS_SCHEMA)
    if a is None:a=fallback_analysis(c["name"],chunks)
    else:
        freshness=a.get("course_profile",{}).get("freshness_needed",False)
        ext_schema={"type":"object","properties":{"external_knowledge":{"type":"array","items":{"type":"object","properties":{
          "title":{"type":"string"},"text":{"type":"string"},"why":{"type":"string"},"source_type":{"type":"string","enum":["model_knowledge","web"]}
        },"required":["title","text","why","source_type"],"additionalProperties":False}}},"required":["external_knowledge"],"additionalProperties":False}
        try:
            ext=json_call(f"""과목 '{c['name']}'의 현재 강의 범위를 이해하는 데 꼭 필요한 보충지식만 최대 8개.
시험범위를 쓸데없이 넓히지 말고 강의자료와 명확히 분리해.
최신성이 필요한 분야에서만 웹 정보를 써.
강의 개요:{a.get('overview','')}
핵심:{json.dumps(a.get('must_understand',[])[:12],ensure_ascii=False)}""",ext_schema,web=bool(freshness))
            if ext:a["external_knowledge"]=ext["external_knowledge"]
        except Exception:pass
    con=db();con.execute("UPDATE courses SET profile_json=?,analysis_json=? WHERE id=? AND profile_id=?",(json.dumps(a.get("course_profile",{}),ensure_ascii=False),json.dumps(a,ensure_ascii=False),cid,pid));con.commit();con.close()
    return a

# ---------- evidence-based past exam analysis ----------
@app.post("/api/p/{pid}/courses/{cid}/exam-pattern")
def exam_pattern(pid:int,cid:int):
    c=course_row(pid,cid)
    exams=course_docs(pid,cid,["past_exam"])
    if not exams:
        return {"available":False,"message":"기출/족보 PDF를 '기출문제' 유형으로 올리면 실제 증거 기반 출제패턴을 분석해."}
    chunks=chunks_from_docs(exams)
    material="\n\n".join(f"[{x['doc']} p.{x['page']}]\n{x['text']}" for x in chunks[:160])
    prompt=f"""과목 '{c['name']}'의 실제 업로드 기출자료만 근거로 출제패턴을 분석해.
자료 개수/페이지가 적으면 확신도를 낮춰 표현한다.
교수의 성향·의도·미래 출제를 사실처럼 단정하지 않는다.
반복 주제마다 실제 파일/페이지 근거를 evidence에 포함한다.
'evidence_based_focus'는 예측이 아니라 '과거 증거상 우선 복습할 영역'으로 쓴다.
기출자료:
{material[:240000]}"""
    p=json_call(prompt,PATTERN_SCHEMA)
    if p is None:
        p={"evidence_count":len(exams),"question_formats":[],"recurring_topics":[],"difficulty_profile":"API 연결 후 분석 가능","trap_patterns":[],"answer_style":"","evidence_based_focus":[],"warning":"기출만 근거로 판단해야 해."}
    con=db();con.execute("INSERT OR REPLACE INTO exam_patterns(course_id,analysis_json,updated_at) VALUES(?,?,?)",(cid,json.dumps(p,ensure_ascii=False),nowiso()));con.commit();con.close()
    return {"available":True,"pattern":p}

# ---------- quiz / mock ----------
@app.post("/api/p/{pid}/courses/{cid}/quiz")
def quiz(pid:int,cid:int,count:int=Form(15),difficulty:str=Form("auto"),mode:str=Form("adaptive")):
    c=course_row(pid,cid);docs=course_docs(pid,cid,["lecture","textbook","notes"])
    if not docs:docs=course_docs(pid,cid)
    chunks=chunks_from_docs(docs);weak=weakness_context(pid,cid)
    analysis=json.loads(c["analysis_json"] or "{}")
    con=db();pr=con.execute("SELECT analysis_json FROM exam_patterns WHERE course_id=?",(cid,)).fetchone();con.close()
    pattern=json.loads(pr["analysis_json"]) if pr else None
    query=" ".join(weak) if mode=="adaptive" and weak else json.dumps(analysis.get("exam_hotspots",[])[:12],ensure_ascii=False)
    chosen=retrieve(chunks,query,k=34);material="\n\n".join(f"[{x['doc']} p.{x['page']}]\n{x['text']}" for x in chosen)
    count=max(5,min(40,count))
    prompt=f"""현재 과목 '{c['name']}'의 시험문제를 정확히 {count}개 만든다.
다른 과목/사용자 자료는 절대 사용하지 않는다.
모드={mode}, 난이도={difficulty}, 학습유형={analysis.get('course_profile',{}).get('study_style','mixed')}.
현재 과목 약점={weak if weak else '없음'}.
기출패턴={json.dumps(pattern,ensure_ascii=False)[:12000] if pattern else '기출 증거 없음'}.

adaptive: 약점이 있으면 약 50%를 약점과 연결.
mock: 실제 시험처럼 범위를 넓게 분산하고, 기출패턴이 있을 때만 형식 비중을 참고.
기출이 없는데 교수 스타일을 추측하지 않는다.
MCQ 5개 선택지, OX, short를 과목 성격에 맞춰 섞는다.
모든 문제에 현재 과목의 실제 source_doc/page를 넣는다.
외부지식은 정답의 필수조건이 아니다.

현재 과목 자료:
{material[:145000]}"""
    d=json_call(prompt,QUESTION_SCHEMA)
    if d is None:
        d={"questions":[{"type":"true_false","question":x["text"][:180],"choices":["O","X"],"answer":"O","explanation":f"{x['doc']} p.{x['page']} 근거","tags":["핵심"],"source_doc":x["doc"],"page":x["page"],"source_type":"lecture","difficulty":"medium"} for x in chosen[:count]]}
    return d

@app.post("/api/p/{pid}/courses/{cid}/grade")
async def grade(pid:int,cid:int,payload:dict):
    course_row(pid,cid);qs=payload.get("questions",[]);ans=payload.get("answers",[]);mode=payload.get("mode","adaptive")
    results=[];total=0
    for i,q in enumerate(qs):
        u=(ans[i] if i<len(ans) else "") or ""
        if q["type"] in ("mcq","true_false"):
            ok=u.strip()==q["answer"].strip();r={"correct":ok,"score":100 if ok else 0,"feedback":q["explanation"],"ideal_answer":q["answer"]}
        else:
            r=json_call(f"""현재 과목의 서술형 채점. 다른 과목 지식은 사용하지 않는다.
문제:{q['question']}
기준정답:{q['answer']}
학생답:{u}
핵심 의미가 맞으면 표현 차이는 허용한다.""",GRADE_SCHEMA)
            if r is None:
                ok=q["answer"].strip().lower() in u.lower() and bool(u.strip());r={"correct":ok,"score":100 if ok else 0,"feedback":q["explanation"],"ideal_answer":q["answer"]}
        total+=r["score"];results.append(r)
    score=round(total/max(1,len(qs)),1);wrong=[]
    for q,r in zip(qs,results):
        if not r["correct"]:wrong.append({"question":q["question"],"tags":q.get("tags",[]),"source_doc":q.get("source_doc"),"page":q.get("page"),"feedback":r["feedback"]})
    con=db();con.execute("INSERT INTO attempts(course_id,created_at,score,detail_json,mode) VALUES(?,?,?,?,?)",(cid,nowiso(),score,json.dumps({"wrong":wrong,"results":results},ensure_ascii=False),mode));con.commit();con.close()
    return {"score":score,"results":results,"wrong":wrong,"recommendation":weakness_context(pid,cid)}

# ---------- tutor: course-scoped memory ----------
@app.post("/api/p/{pid}/courses/{cid}/tutor")
async def tutor(pid:int,cid:int,payload:dict):
    c=course_row(pid,cid);q=(payload.get("question") or "").strip()
    if not q:raise HTTPException(400,"질문을 입력해줘.")
    docs=course_docs(pid,cid,["lecture","textbook","notes"])
    if not docs:docs=course_docs(pid,cid)
    rel=retrieve(chunks_from_docs(docs),q,k=16);context="\n\n".join(f"[{x['doc']} p.{x['page']}]\n{x['text']}" for x in rel)
    con=db();hist=con.execute("SELECT role,content FROM tutor_messages WHERE course_id=? ORDER BY id DESC LIMIT 8",(cid,)).fetchall();con.close()
    history="\n".join(f"{x['role']}: {x['content']}" for x in reversed(hist))
    analysis=json.loads(c["analysis_json"] or "{}");fresh=analysis.get("course_profile",{}).get("freshness_needed",False)
    latest=any(k in q.lower() for k in ["최신","현재","요즘","최근","2026","오늘"])
    prompt=f"""너는 오직 profile:{pid}/course:{cid} 과목 '{c['name']}'만 담당한다.
아래 대화기록도 현재 과목 안에서만 축적된 기록이다.
다른 과목이나 다른 사용자의 정보는 사용하지 않는다.
먼저 강의자료 근거로 답하고 부족하면 '보충 설명'이라고 명시한다.
최신 질문이면서 분야상 최신성이 필요할 때만 웹 검색을 사용한다.
답 끝에는 사용한 자료명 p.페이지를 적는다.
모르면 추측하지 않는다.

현재 과목 대화:
{history}

질문:{q}

관련 현재 과목 자료:
{context[:80000]}"""
    answer=text_call(prompt,web=bool(fresh and latest))
    if answer is None:answer="API가 연결되지 않았어. 관련 근거: "+", ".join(f"{x['doc']} p.{x['page']}" for x in rel[:6])
    con=db();con.execute("INSERT INTO tutor_messages(course_id,role,content,created_at) VALUES(?,?,?,?)",(cid,"user",q,nowiso()));con.execute("INSERT INTO tutor_messages(course_id,role,content,created_at) VALUES(?,?,?,?)",(cid,"assistant",answer,nowiso()));con.commit();con.close()
    return {"answer":answer}

# ---------- cards ----------
@app.get("/api/p/{pid}/courses/{cid}/due-cards")
def due_cards(pid:int,cid:int):
    c=course_row(pid,cid);a=json.loads(c["analysis_json"] or "{}")
    allcards=due_info(cid,a.get("flashcards",[]))
    return {"due":[x for x in allcards if x["is_due"]],"all":allcards}

@app.post("/api/p/{pid}/courses/{cid}/review-card")
async def review_card(pid:int,cid:int,payload:dict):
    course_row(pid,cid);key=str(payload.get("card_key",""));rating=max(1,min(4,int(payload.get("rating",2))))
    con=db();con.execute("INSERT INTO card_reviews(course_id,card_key,rating,created_at) VALUES(?,?,?,?)",(cid,key,rating,nowiso()));con.commit();con.close()
    return {"ok":True}

# ---------- backup ----------
@app.get("/api/p/{pid}/backup")
def backup(pid:int):
    p=profile_row(pid);con=db()
    courses=[dict(x) for x in con.execute("SELECT * FROM courses WHERE profile_id=?",(pid,)).fetchall()]
    ids=[x["id"] for x in courses]
    data={"profile":{"id":p["id"],"name":p["name"]},"courses":courses,"documents":[],"attempts":[],"card_reviews":[],"tutor_messages":[]}
    for cid in ids:
        data["documents"] += [dict(x) for x in con.execute("SELECT id,course_id,name,pages,document_type,extraction_mode,image_count,created_at FROM documents WHERE course_id=?",(cid,)).fetchall()]
        data["attempts"] += [dict(x) for x in con.execute("SELECT * FROM attempts WHERE course_id=?",(cid,)).fetchall()]
        data["card_reviews"] += [dict(x) for x in con.execute("SELECT * FROM card_reviews WHERE course_id=?",(cid,)).fetchall()]
        data["tutor_messages"] += [dict(x) for x in con.execute("SELECT * FROM tutor_messages WHERE course_id=?",(cid,)).fetchall()]
    con.close()
    return JSONResponse(data,headers={"Content-Disposition":f'attachment; filename="exam_ai_profile_{pid}_backup.json"'})

@app.get("/")
def root():return FileResponse(BASE/"static"/"index.html")
app.mount("/",StaticFiles(directory=BASE/"static"),name="static")
