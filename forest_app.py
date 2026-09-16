import json
import os
import urllib.request
import urllib.error
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import server

app = server.app
MARK_TYPES={'core','annotation','lecture','manual','past_exam'}

def ensure_marks(con):
    con.execute('''CREATE TABLE IF NOT EXISTS user_marks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      content TEXT NOT NULL,
      source_type TEXT NOT NULL DEFAULT 'core',
      source_doc TEXT DEFAULT '',
      source_document_id INTEGER,
      page INTEGER,
      timestamp_seconds REAL,
      locator TEXT DEFAULT '',
      category TEXT DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    )''')
    columns={r['name'] for r in con.execute('PRAGMA table_info(user_marks)').fetchall()}
    if 'source_document_id' not in columns:con.execute('ALTER TABLE user_marks ADD COLUMN source_document_id INTEGER')
    if 'timestamp_seconds' not in columns:con.execute('ALTER TABLE user_marks ADD COLUMN timestamp_seconds REAL')
    con.execute('CREATE INDEX IF NOT EXISTS idx_user_marks_course ON user_marks(course_id,id DESC)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_user_marks_source_document ON user_marks(course_id,source_document_id)')

def ensure_lectures(con):
    con.execute('''CREATE TABLE IF NOT EXISTS lecture_sessions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      title TEXT NOT NULL DEFAULT '',
      started_at TEXT NOT NULL,
      ended_at TEXT DEFAULT '',
      duration_seconds REAL DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'recording',
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS lecture_transcript(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id INTEGER NOT NULL,
      text TEXT NOT NULL,
      start_seconds REAL NOT NULL DEFAULT 0,
      end_seconds REAL NOT NULL DEFAULT 0,
      importance TEXT NOT NULL DEFAULT 'normal',
      client_event_id TEXT DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY(session_id) REFERENCES lecture_sessions(id) ON DELETE CASCADE
    )''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_lecture_sessions_course ON lecture_sessions(course_id,id DESC)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_lecture_transcript_session ON lecture_transcript(session_id,start_seconds,id)')
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_lecture_event_unique ON lecture_transcript(session_id,client_event_id) WHERE client_event_id<>''")

def mark_rows(cid):
    con=server.db();ensure_marks(con);rows=[dict(r) for r in con.execute('SELECT * FROM user_marks WHERE course_id=? ORDER BY id DESC',(cid,)).fetchall()];con.commit();con.close();return rows

_startup_con=server.db();ensure_marks(_startup_con);ensure_lectures(_startup_con);_startup_con.commit();_startup_con.close()

def owned_session(pid,cid,sid):
    server.course_row(pid,cid);con=server.db();ensure_lectures(con);row=con.execute('SELECT * FROM lecture_sessions WHERE id=? AND course_id=?',(sid,cid)).fetchone();con.commit();con.close()
    if not row:raise HTTPException(404,'강의 녹음 세션을 찾지 못했어.')
    return dict(row)

@app.get('/api/p/{pid}/courses/{cid}/marks')
def marks(pid:int,cid:int):
    server.course_row(pid,cid);rows=mark_rows(cid);return {'marks':rows,'count':len(rows)}

@app.post('/api/p/{pid}/courses/{cid}/marks')
async def add_mark(pid:int,cid:int,request:Request):
    server.course_row(pid,cid)
    try:data=await request.json()
    except Exception:raise HTTPException(400,'표시할 내용을 읽지 못했어.')
    if not isinstance(data,dict):raise HTTPException(400,'표시할 내용을 읽지 못했어.')
    content=str(data.get('content') or '').strip()
    if not content or len(content)>10000:raise HTTPException(400,'표시 내용은 1~10000자로 입력해줘.')
    source_type=str(data.get('source_type') or 'core').strip()
    if source_type not in MARK_TYPES:raise HTTPException(400,'지원하지 않는 표시 출처야.')
    source_doc=str(data.get('source_doc') or '').strip();source_document_id=data.get('source_document_id')
    locator=str(data.get('locator') or '').strip();category=str(data.get('category') or '').strip();page=data.get('page');timestamp=data.get('timestamp_seconds')
    if len(source_doc)>300 or len(locator)>500 or len(category)>80:raise HTTPException(400,'표시 출처 정보가 너무 길어.')
    if page not in (None,''):
        try:page=int(page)
        except Exception:raise HTTPException(400,'페이지 번호가 올바르지 않아.')
        if page<1 or page>100000:raise HTTPException(400,'페이지 번호가 올바르지 않아.')
    else:page=None
    if source_document_id not in (None,''):
        try:source_document_id=int(source_document_id)
        except Exception:raise HTTPException(400,'원본 자료 정보가 올바르지 않아.')
        con=server.db();doc=con.execute('SELECT id FROM documents WHERE id=? AND course_id=?',(source_document_id,cid)).fetchone();con.close()
        if not doc:raise HTTPException(400,'이 과목의 원본 자료가 아니야.')
    else:source_document_id=None
    if timestamp not in (None,''):
        try:timestamp=float(timestamp)
        except Exception:raise HTTPException(400,'강의 시간이 올바르지 않아.')
        if timestamp<0 or timestamp>864000:raise HTTPException(400,'강의 시간이 올바르지 않아.')
        timestamp=round(timestamp,3)
    else:timestamp=None
    con=server.db();ensure_marks(con);old=con.execute('SELECT id FROM user_marks WHERE course_id=? AND content=? AND source_type=? AND source_doc=? AND COALESCE(source_document_id,-1)=COALESCE(?,-1) AND COALESCE(page,-1)=COALESCE(?,-1) AND locator=? LIMIT 1',(cid,content,source_type,source_doc,source_document_id,page,locator)).fetchone()
    if old:con.commit();con.close();return {'ok':True,'id':old['id'],'duplicate':True}
    cur=con.execute('INSERT INTO user_marks(course_id,content,source_type,source_doc,source_document_id,page,timestamp_seconds,locator,category,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,content,source_type,source_doc,source_document_id,page,timestamp,locator,category,server.nowiso()));con.commit();mid=cur.lastrowid;con.close();return {'ok':True,'id':mid,'duplicate':False}

@app.delete('/api/p/{pid}/courses/{cid}/marks/{mid}')
def remove_mark(pid:int,cid:int,mid:int):
    server.course_row(pid,cid);con=server.db();ensure_marks(con);row=con.execute('SELECT source_type FROM user_marks WHERE id=? AND course_id=?',(mid,cid)).fetchone()
    if not row:con.close();raise HTTPException(404,'표시한 내용을 찾지 못했어.')
    if row['source_type']=='annotation':con.close();raise HTTPException(409,'자료 위 텍스트 필기는 원본 필기 화면에서 수정해줘.')
    con.execute('DELETE FROM user_marks WHERE id=? AND course_id=?',(mid,cid));con.commit();con.close();return {'ok':True}

@app.get('/api/realtime-token')
def realtime_token(request:Request):
    key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:raise HTTPException(503,'OpenAI API 키가 서버에 연결되지 않았어.')
    model=os.getenv('OPENAI_REALTIME_MODEL','gpt-realtime')
    body=json.dumps({'session':{'type':'transcription','audio':{'input':{'transcription':{'model':os.getenv('OPENAI_TRANSCRIBE_MODEL','gpt-4o-mini-transcribe'),'language':'ko'}}}}}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/realtime/client_secrets',data=body,method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as res:data=json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        detail=e.read().decode(errors='ignore')[:500];raise HTTPException(502,'Realtime 토큰 발급 실패: '+detail)
    except Exception:raise HTTPException(502,'Realtime 토큰 발급에 실패했어.')
    value=data.get('value') or data.get('client_secret',{}).get('value')
    if not value:raise HTTPException(502,'Realtime 임시 토큰을 받지 못했어.')
    return {'value':value,'model':model}

@app.post('/api/p/{pid}/courses/{cid}/lectures')
async def create_lecture(pid:int,cid:int,request:Request):
    server.course_row(pid,cid)
    try:data=await request.json()
    except Exception:data={}
    title=str((data or {}).get('title') or '강의 녹음').strip()[:200]
    con=server.db();ensure_lectures(con);cur=con.execute('INSERT INTO lecture_sessions(course_id,title,started_at,status) VALUES(?,?,?,?)',(cid,title,server.nowiso(),'recording'));con.commit();sid=cur.lastrowid;con.close();return {'id':sid,'title':title,'status':'recording'}

@app.get('/api/p/{pid}/courses/{cid}/lectures')
def list_lectures(pid:int,cid:int):
    server.course_row(pid,cid);con=server.db();ensure_lectures(con);rows=[dict(r) for r in con.execute('SELECT * FROM lecture_sessions WHERE course_id=? ORDER BY id DESC',(cid,)).fetchall()];con.commit();con.close();return {'lectures':rows}

@app.get('/api/p/{pid}/courses/{cid}/lectures/{sid}/transcript')
def lecture_transcript(pid:int,cid:int,sid:int):
    owned_session(pid,cid,sid);con=server.db();ensure_lectures(con);rows=[dict(r) for r in con.execute('SELECT * FROM lecture_transcript WHERE session_id=? ORDER BY start_seconds,id',(sid,)).fetchall()];con.commit();con.close();return {'segments':rows}

@app.post('/api/p/{pid}/courses/{cid}/lectures/{sid}/transcript')
async def add_transcript(pid:int,cid:int,sid:int,request:Request):
    session=owned_session(pid,cid,sid)
    if session['status']=='finished':raise HTTPException(409,'이미 종료된 강의 녹음이야.')
    try:data=await request.json()
    except Exception:raise HTTPException(400,'자막 데이터를 읽지 못했어.')
    text=str((data or {}).get('text') or '').strip()
    if not text or len(text)>10000:raise HTTPException(400,'자막 내용이 올바르지 않아.')
    try:start=max(0,float(data.get('start_seconds') or 0));end=max(start,float(data.get('end_seconds') or start))
    except Exception:raise HTTPException(400,'자막 시간이 올바르지 않아.')
    importance=str(data.get('importance') or 'normal');importance=importance if importance in {'normal','ai','professor','user'} else 'normal';event=str(data.get('client_event_id') or '')[:200]
    con=server.db();ensure_lectures(con)
    if event:
        old=con.execute('SELECT id FROM lecture_transcript WHERE session_id=? AND client_event_id=?',(sid,event)).fetchone()
        if old:con.commit();con.close();return {'ok':True,'id':old['id'],'duplicate':True}
    cur=con.execute('INSERT INTO lecture_transcript(session_id,text,start_seconds,end_seconds,importance,client_event_id,created_at) VALUES(?,?,?,?,?,?,?)',(sid,text,round(start,3),round(end,3),importance,event,server.nowiso()));con.commit();segid=cur.lastrowid;con.close();return {'ok':True,'id':segid,'duplicate':False}

@app.post('/api/p/{pid}/courses/{cid}/lectures/{sid}/finish')
async def finish_lecture(pid:int,cid:int,sid:int,request:Request):
    owned_session(pid,cid,sid)
    try:data=await request.json()
    except Exception:data={}
    try:duration=max(0,float((data or {}).get('duration_seconds') or 0))
    except Exception:duration=0
    con=server.db();ensure_lectures(con);con.execute("UPDATE lecture_sessions SET ended_at=?,duration_seconds=?,status='finished' WHERE id=? AND course_id=?",(server.nowiso(),round(duration,3),sid,cid));con.commit();con.close();return {'ok':True,'status':'finished'}

_core_clean=server.clean_annotation_items
def clean_annotation_items(items):
    clean,encoded=_core_clean([{k:v for k,v in item.items() if k!='opacity'} if isinstance(item,dict) else item for item in items] if isinstance(items,list) else items)
    for original,saved in zip(items or [],clean):
        if saved.get('type')=='stroke' and isinstance(original,dict) and 'opacity' in original:
            try:opacity=float(original['opacity'])
            except Exception:raise HTTPException(400,'필기 투명도가 올바르지 않아.')
            if not 0.1<=opacity<=1:raise HTTPException(400,'필기 투명도가 올바르지 않아.')
            saved['opacity']=round(opacity,2)
    encoded=json.dumps(clean,ensure_ascii=False,separators=(',',':'))
    if len(encoded.encode('utf-8'))>2*1024*1024:raise HTTPException(413,'한 페이지 필기는 2MB까지 저장할 수 있어.')
    return clean,encoded

annotation_path='/api/p/{pid}/courses/{cid}/documents/{did}/annotations'
app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)==annotation_path and 'PUT' in getattr(r,'methods',set()))]
@app.put(annotation_path)
async def save_annotations_with_marks(pid:int,cid:int,did:int,request:Request,page:int=1):
    row,_=server.owned_document(pid,cid,did);page=server.annotation_page(row,page)
    try:payload=await request.json()
    except Exception:raise HTTPException(400,'필기 데이터를 읽지 못했어.')
    items,encoded=clean_annotation_items(payload.get('items') if isinstance(payload,dict) else None);stamp=server.nowiso();con=server.db();ensure_marks(con)
    try:
        con.execute('BEGIN IMMEDIATE');con.execute('''INSERT INTO document_annotations(document_id,page,data_json,updated_at) VALUES(?,?,?,?) ON CONFLICT(document_id,page) DO UPDATE SET data_json=excluded.data_json,updated_at=excluded.updated_at''',(did,page,encoded,stamp));prefix=f'annotation:{did}:{page}:';con.execute("DELETE FROM user_marks WHERE course_id=? AND source_type='annotation' AND locator LIKE ?",(cid,prefix+'%'))
        for index,item in enumerate(items):
            if item.get('type')!='text':continue
            text=str(item.get('text') or '').strip()
            if text:con.execute('INSERT INTO user_marks(course_id,content,source_type,source_doc,source_document_id,page,timestamp_seconds,locator,category,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,text,'annotation',row['name'],did,page,None,prefix+str(index),'annotation_text',stamp))
        con.commit()
    except Exception:con.rollback();raise
    finally:con.close()
    return {'ok':True,'page':page,'count':len(items),'updated_at':stamp,'text_marks':sum(1 for x in items if x.get('type')=='text')}

app.router.routes[:]=[r for r in app.router.routes if getattr(r,'path',None)!='/api/p/{pid}/backup']
@app.get('/api/p/{pid}/backup')
def backup_v3(pid:int):
    p=server.profile_row(pid);con=server.db();ensure_marks(con);ensure_lectures(con);courses=[dict(x) for x in con.execute('SELECT * FROM courses WHERE profile_id=?',(pid,)).fetchall()];ids=[x['id'] for x in courses]
    data={'profile':{'id':p['id'],'name':p['name']},'courses':courses,'documents':[],'attempts':[],'card_reviews':[],'tutor_messages':[],'exam_patterns':[],'document_annotations':[],'user_marks':[],'lecture_sessions':[],'lecture_transcript':[],'format_version':4}
    for cid in ids:
        docs=[dict(x) for x in con.execute('SELECT id,course_id,name,pages,text_json,sha256,document_type,extraction_mode,image_count,created_at FROM documents WHERE course_id=?',(cid,)).fetchall()];data['documents']+=docs;data['attempts'] += [dict(x) for x in con.execute('SELECT * FROM attempts WHERE course_id=?',(cid,)).fetchall()];data['card_reviews'] += [dict(x) for x in con.execute('SELECT * FROM card_reviews WHERE course_id=?',(cid,)).fetchall()];data['exam_patterns'] += [dict(x) for x in con.execute('SELECT * FROM exam_patterns WHERE course_id=?',(cid,)).fetchall()];data['user_marks'] += [dict(x) for x in con.execute('SELECT * FROM user_marks WHERE course_id=?',(cid,)).fetchall()]
        sessions=[dict(x) for x in con.execute('SELECT * FROM lecture_sessions WHERE course_id=?',(cid,)).fetchall()];data['lecture_sessions']+=sessions
        for s in sessions:data['lecture_transcript'] += [dict(x) for x in con.execute('SELECT * FROM lecture_transcript WHERE session_id=?',(s['id'],)).fetchall()]
        for d in docs:data['document_annotations'] += [dict(x) for x in con.execute('SELECT document_id,page,data_json,updated_at FROM document_annotations WHERE document_id=?',(d['id'],)).fetchall()]
    con.commit();con.close();return JSONResponse(data,headers={'Content-Disposition':f'attachment; filename="forest_profile_{pid}_backup_v4.json"'})
