import hashlib
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path
from fastapi import File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.routing import Mount
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
    con.executescript('''
    CREATE TABLE IF NOT EXISTS lecture_sessions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      duration_seconds REAL NOT NULL DEFAULT 0,
      audio_path TEXT DEFAULT '',
      audio_mime TEXT DEFAULT '',
      status TEXT NOT NULL DEFAULT 'recording',
      created_at TEXT NOT NULL,
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS transcript_segments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      lecture_id INTEGER NOT NULL,
      start_seconds REAL NOT NULL DEFAULT 0,
      end_seconds REAL NOT NULL DEFAULT 0,
      text TEXT NOT NULL,
      importance TEXT NOT NULL DEFAULT 'normal',
      client_event_id TEXT DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY(lecture_id) REFERENCES lecture_sessions(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_lecture_sessions_course ON lecture_sessions(course_id,id DESC);
    CREATE INDEX IF NOT EXISTS idx_transcript_segments_lecture ON transcript_segments(lecture_id,start_seconds,id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_transcript_event_unique ON transcript_segments(lecture_id,client_event_id) WHERE client_event_id<>'';
    ''')

def lecture_row(pid,cid,sid):
    server.course_row(pid,cid);con=server.db();ensure_lectures(con)
    row=con.execute('SELECT * FROM lecture_sessions WHERE id=? AND course_id=?',(sid,cid)).fetchone();con.commit();con.close()
    if not row:raise HTTPException(404,'이 과목의 강의 녹음을 찾지 못했어.')
    return dict(row)

def clean_seconds(value,label):
    try:number=float(value or 0)
    except Exception:raise HTTPException(400,f'{label} 시간이 올바르지 않아.')
    if number<0 or number>864000:raise HTTPException(400,f'{label} 시간이 올바르지 않아.')
    return round(number,3)

def clean_importance(value):
    value=str(value or 'normal')
    if value not in {'normal','professor','ai','user'}:raise HTTPException(400,'지원하지 않는 중요도야.')
    return value

def mark_rows(cid):
    con=server.db();ensure_marks(con);rows=[dict(r) for r in con.execute('SELECT * FROM user_marks WHERE course_id=? ORDER BY id DESC',(cid,)).fetchall()];con.commit();con.close();return rows

_startup_con=server.db();ensure_marks(_startup_con);ensure_lectures(_startup_con);_startup_con.commit();_startup_con.close()

@app.post('/api/p/{pid}/courses/{cid}/lectures')
async def create_lecture(pid:int,cid:int,request:Request):
    server.course_row(pid,cid)
    try:data=await request.json()
    except Exception:data={}
    title=str((data if isinstance(data,dict) else {}).get('title') or '').strip()
    if not title:title='강의 '+server.datetime.now().strftime('%Y-%m-%d %H:%M')
    if len(title)>200:raise HTTPException(400,'강의 제목은 200자까지 입력할 수 있어.')
    con=server.db();ensure_lectures(con);cur=con.execute('INSERT INTO lecture_sessions(course_id,title,created_at) VALUES(?,?,?)',(cid,title,server.nowiso()));con.commit();sid=cur.lastrowid;con.close()
    return {'id':sid,'title':title,'status':'recording'}

@app.get('/api/p/{pid}/courses/{cid}/lectures')
def list_lectures(pid:int,cid:int):
    server.course_row(pid,cid);con=server.db();ensure_lectures(con)
    rows=[dict(r) for r in con.execute('''SELECT l.*,COUNT(t.id) transcript_count FROM lecture_sessions l LEFT JOIN transcript_segments t ON t.lecture_id=l.id WHERE l.course_id=? GROUP BY l.id ORDER BY l.id DESC''',(cid,)).fetchall()];con.commit();con.close()
    for row in rows:row['has_audio']=bool(row.pop('audio_path',''))
    return {'lectures':rows}

@app.post('/api/p/{pid}/courses/{cid}/lectures/{sid}/audio')
async def save_lecture_audio(pid:int,cid:int,sid:int,audio:UploadFile=File(...),duration_seconds:str=Form('0')):
    old=lecture_row(pid,cid,sid);duration=clean_seconds(duration_seconds,'녹음')
    mime=(audio.content_type or '').lower();extensions={'audio/webm':'.webm','audio/mp4':'.m4a','audio/mpeg':'.mp3','audio/ogg':'.ogg','audio/wav':'.wav','audio/x-wav':'.wav'}
    if mime not in extensions:raise HTTPException(415,'지원하지 않는 녹음 형식이야.')
    folder=server.DATA/f'p{pid}'/f'c{cid}'/'lectures';folder.mkdir(parents=True,exist_ok=True)
    temporary=folder/f'.lecture-{sid}.upload';size=0;digest=hashlib.sha256()
    try:
        with temporary.open('wb') as target:
            while chunk:=await audio.read(1024*1024):
                size+=len(chunk)
                if size>250*1024*1024:raise HTTPException(413,'강의 녹음은 250MB까지 저장할 수 있어.')
                digest.update(chunk);target.write(chunk)
        if size<16:raise HTTPException(400,'녹음 파일이 비어 있어.')
        destination=folder/f'{sid}-{digest.hexdigest()[:16]}{extensions[mime]}'
        temporary.replace(destination)
        con=server.db();ensure_lectures(con);con.execute("UPDATE lecture_sessions SET duration_seconds=?,audio_path=?,audio_mime=?,status='saved' WHERE id=? AND course_id=?",(duration,str(destination),mime,sid,cid));con.commit();con.close()
        previous=Path(old.get('audio_path') or '')
        if previous!=destination and previous.is_file() and previous.is_relative_to(folder.resolve()):previous.unlink(missing_ok=True)
        return {'ok':True,'id':sid,'bytes':size,'duration_seconds':duration,'status':'saved'}
    except Exception:
        temporary.unlink(missing_ok=True);raise

@app.get('/api/p/{pid}/courses/{cid}/lectures/{sid}/audio')
def get_lecture_audio(pid:int,cid:int,sid:int):
    row=lecture_row(pid,cid,sid);path=Path(row.get('audio_path') or '').resolve();root=server.DATA.resolve()
    if not path.is_relative_to(root) or not path.is_file():raise HTTPException(404,'저장된 강의 녹음이 없어.')
    return FileResponse(path,media_type=row.get('audio_mime') or mimetypes.guess_type(path.name)[0] or 'application/octet-stream',headers={'Cache-Control':'private, no-store'})

@app.get('/api/p/{pid}/courses/{cid}/lectures/{sid}/transcript')
def get_transcript(pid:int,cid:int,sid:int):
    lecture_row(pid,cid,sid);con=server.db();ensure_lectures(con);rows=[dict(r) for r in con.execute('SELECT * FROM transcript_segments WHERE lecture_id=? ORDER BY start_seconds,id',(sid,)).fetchall()];con.commit();con.close();return {'segments':rows}

@app.post('/api/p/{pid}/courses/{cid}/lectures/{sid}/transcript')
async def add_transcript(pid:int,cid:int,sid:int,request:Request):
    lecture_row(pid,cid,sid)
    try:data=await request.json()
    except Exception:raise HTTPException(400,'자막을 읽지 못했어.')
    text=str(data.get('text') or '').strip() if isinstance(data,dict) else ''
    if not text or len(text)>10000:raise HTTPException(400,'자막은 1~10000자로 입력해줘.')
    start=clean_seconds(data.get('start_seconds'),'시작');end=clean_seconds(data.get('end_seconds',start),'종료')
    if end<start:end=start
    importance=clean_importance(data.get('importance'));event=str(data.get('client_event_id') or '').strip()
    if len(event)>200:raise HTTPException(400,'자막 이벤트 정보가 너무 길어.')
    con=server.db();ensure_lectures(con)
    if event:
        old=con.execute('SELECT id FROM transcript_segments WHERE lecture_id=? AND client_event_id=?',(sid,event)).fetchone()
        if old:con.commit();con.close();return {'ok':True,'id':old['id'],'duplicate':True}
    cur=con.execute('INSERT INTO transcript_segments(lecture_id,start_seconds,end_seconds,text,importance,client_event_id,created_at) VALUES(?,?,?,?,?,?,?)',(sid,start,end,text,importance,event,server.nowiso()));con.commit();segment_id=cur.lastrowid;con.close();return {'ok':True,'id':segment_id,'duplicate':False}

@app.patch('/api/p/{pid}/courses/{cid}/lectures/{sid}/transcript/{segment_id}')
async def update_transcript(pid:int,cid:int,sid:int,segment_id:int,request:Request):
    lecture_row(pid,cid,sid)
    try:data=await request.json()
    except Exception:raise HTTPException(400,'자막 변경 내용을 읽지 못했어.')
    changes=[];values=[]
    if 'text' in data:
        text=str(data.get('text') or '').strip()
        if not text or len(text)>10000:raise HTTPException(400,'자막은 1~10000자로 입력해줘.')
        changes.append('text=?');values.append(text)
    if 'importance' in data:changes.append('importance=?');values.append(clean_importance(data.get('importance')))
    if not changes:raise HTTPException(400,'변경할 자막 내용이 없어.')
    con=server.db();ensure_lectures(con);cur=con.execute(f"UPDATE transcript_segments SET {','.join(changes)} WHERE id=? AND lecture_id=?",(*values,segment_id,sid));con.commit();con.close()
    if not cur.rowcount:raise HTTPException(404,'자막 문장을 찾지 못했어.')
    return {'ok':True}

@app.delete('/api/p/{pid}/courses/{cid}/lectures/{sid}/transcript/{segment_id}')
def delete_transcript(pid:int,cid:int,sid:int,segment_id:int):
    lecture_row(pid,cid,sid);con=server.db();ensure_lectures(con);cur=con.execute('DELETE FROM transcript_segments WHERE id=? AND lecture_id=?',(segment_id,sid));con.commit();con.close()
    if not cur.rowcount:raise HTTPException(404,'자막 문장을 찾지 못했어.')
    return {'ok':True}

def _openai_realtime_secret(api_key,safety_identifier):
    body=json.dumps({'expires_after':{'anchor':'created_at','seconds':120},'session':{'type':'transcription','audio':{'input':{'noise_reduction':{'type':'far_field'},'transcription':{'model':os.getenv('OPENAI_TRANSCRIBE_MODEL','gpt-live-transcribe'),'language':'ko'},'turn_detection':{'type':'server_vad'}}}}}).encode()
    req=urllib.request.Request('https://api.openai.com/v1/realtime/client_secrets',data=body,headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json','OpenAI-Safety-Identifier':safety_identifier},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=20) as response:return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode('utf-8','replace')[:1000]
        server.logging.warning('Realtime secret request failed: %s %s',exc.code,detail)
        if exc.code in (401,403):raise HTTPException(502,'OpenAI API 키를 확인해야 해.')
        if exc.code==429:raise HTTPException(503,'AI 이용 한도에 도달했어.')
        raise HTTPException(502,'실시간 자막 연결을 준비하지 못했어.')

@app.post('/api/p/{pid}/courses/{cid}/realtime-token')
async def realtime_token(pid:int,cid:int):
    server.course_row(pid,cid);key=os.getenv('OPENAI_API_KEY','').strip()
    if not key:raise HTTPException(503,'OpenAI API 키가 연결되지 않았어.')
    safety=hashlib.sha256(f"forest:{pid}:{server.SESSION_SECRET}".encode()).hexdigest()
    result=await run_in_threadpool(_openai_realtime_secret,key,safety)
    value=result.get('value') if isinstance(result,dict) else None
    if not value:raise HTTPException(502,'실시간 자막 연결 토큰을 받지 못했어.')
    return {'value':value,'expires_at':result.get('expires_at')}

def classify_importance(text,before='',after=''):
    context=' '.join((before,text,after))
    if server.re.search(r'시험.{0,12}(나[오옵]|출제)|중요|반드시|꼭.{0,8}(외우|기억)',context):return 'professor'
    if server.re.search(r'핵심|주의|다시 말하면|정리하면|포인트',context):return 'ai'
    return 'normal'

@app.post('/api/p/{pid}/courses/{cid}/lectures/{sid}/classify-transcript')
async def classify_transcript(pid:int,cid:int,sid:int,request:Request):
    lecture_row(pid,cid,sid);data=await request.json();text=str(data.get('text') or '')
    return {'importance':classify_importance(text,str(data.get('before') or ''),str(data.get('after') or ''))}

@app.post('/api/p/{pid}/courses/{cid}/lectures/{sid}/finalize-note')
def finalize_lecture_note(pid:int,cid:int,sid:int):
    lecture=lecture_row(pid,cid,sid);segments=get_transcript(pid,cid,sid)['segments'];labels={'professor':'교수 강조','ai':'AI 중요','user':'내 표시','normal':'일반'}
    lines=[f"# {lecture['title']}",'']+[f"[{server.timedelta(seconds=float(x['start_seconds']))}] [{labels.get(x['importance'],'일반')}] {x['text']}" for x in segments]
    counts={key:sum(1 for x in segments if x['importance']==key) for key in ('professor','ai','user')}
    return {'title':lecture['title'],'text':'\n'.join(lines),'professor_count':counts['professor'],'ai_count':counts['ai'],'user_count':counts['user']}

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
    server.course_row(pid,cid);con=server.db();ensure_marks(con);cur=con.execute('DELETE FROM user_marks WHERE id=? AND course_id=?',(mid,cid));con.commit();con.close()
    if not cur.rowcount:raise HTTPException(404,'표시한 내용을 찾지 못했어.')
    return {'ok':True}

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
    data={'profile':{'id':p['id'],'name':p['name']},'courses':courses,'documents':[],'attempts':[],'card_reviews':[],'tutor_messages':[],'exam_patterns':[],'document_annotations':[],'user_marks':[],'lecture_sessions':[],'transcript_segments':[],'format_version':4}
    for cid in ids:
        docs=[dict(x) for x in con.execute('SELECT id,course_id,name,pages,text_json,sha256,document_type,extraction_mode,image_count,created_at FROM documents WHERE course_id=?',(cid,)).fetchall()];data['documents']+=docs;data['attempts'] += [dict(x) for x in con.execute('SELECT * FROM attempts WHERE course_id=?',(cid,)).fetchall()];data['card_reviews'] += [dict(x) for x in con.execute('SELECT * FROM card_reviews WHERE course_id=?',(cid,)).fetchall()];data['tutor_messages'] += [dict(x) for x in con.execute('SELECT * FROM tutor_messages WHERE course_id=?',(cid,)).fetchall()];data['exam_patterns'] += [dict(x) for x in con.execute('SELECT * FROM exam_patterns WHERE course_id=?',(cid,)).fetchall()];data['user_marks'] += [dict(x) for x in con.execute('SELECT * FROM user_marks WHERE course_id=?',(cid,)).fetchall()]
        for d in docs:data['document_annotations'] += [dict(x) for x in con.execute('SELECT document_id,page,data_json,updated_at FROM document_annotations WHERE document_id=?',(d['id'],)).fetchall()]
        lectures=[dict(x) for x in con.execute("SELECT id,course_id,title,duration_seconds,audio_mime,status,created_at FROM lecture_sessions WHERE course_id=?",(cid,)).fetchall()];data['lecture_sessions']+=lectures
        for lecture in lectures:data['transcript_segments'] += [dict(x) for x in con.execute('SELECT * FROM transcript_segments WHERE lecture_id=?',(lecture['id'],)).fetchall()]
    con.commit();con.close();return JSONResponse(data,headers={'Content-Disposition':f'attachment; filename="forest_profile_{pid}_backup_v3.json"'})

# server.py mounts static files at '/'. Keep that catch-all route last so the
# extension APIs above remain reachable when uvicorn starts forest_app:app.
_static_mounts=[route for route in app.router.routes if isinstance(route,Mount) and getattr(route,'name',None)=='static']
if _static_mounts:app.router.routes[:]=[route for route in app.router.routes if route not in _static_mounts]+_static_mounts
