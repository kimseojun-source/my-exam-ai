import json
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
import server

app = server.app

def ensure_marks(con):
    con.execute('''CREATE TABLE IF NOT EXISTS user_marks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_id INTEGER NOT NULL,
      content TEXT NOT NULL,
      source_type TEXT NOT NULL DEFAULT 'core',
      source_doc TEXT DEFAULT '',
      page INTEGER,
      locator TEXT DEFAULT '',
      category TEXT DEFAULT '',
      created_at TEXT NOT NULL,
      FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    )''')
    con.execute('CREATE INDEX IF NOT EXISTS idx_user_marks_course ON user_marks(course_id,id DESC)')

def mark_rows(cid):
    con=server.db();ensure_marks(con)
    rows=[dict(r) for r in con.execute('SELECT * FROM user_marks WHERE course_id=? ORDER BY id DESC',(cid,)).fetchall()]
    con.commit();con.close();return rows

@app.get('/api/p/{pid}/courses/{cid}/marks')
def marks(pid:int,cid:int):
    server.course_row(pid,cid);rows=mark_rows(cid)
    return {'marks':rows,'count':len(rows)}

@app.post('/api/p/{pid}/courses/{cid}/marks')
async def add_mark(pid:int,cid:int,request:Request):
    server.course_row(pid,cid)
    try: data=await request.json()
    except Exception: raise HTTPException(400,'표시할 내용을 읽지 못했어.')
    content=str(data.get('content') or '').strip() if isinstance(data,dict) else ''
    if not content or len(content)>10000: raise HTTPException(400,'표시 내용은 1~10000자로 입력해줘.')
    source_type=str(data.get('source_type') or 'core')[:40]
    source_doc=str(data.get('source_doc') or '')[:300]
    locator=str(data.get('locator') or '')[:500]
    category=str(data.get('category') or '')[:80]
    page=data.get('page')
    if page not in (None,''):
        try: page=int(page)
        except Exception: raise HTTPException(400,'페이지 번호가 올바르지 않아.')
        if page<1: raise HTTPException(400,'페이지 번호가 올바르지 않아.')
    else: page=None
    con=server.db();ensure_marks(con)
    old=con.execute('SELECT id FROM user_marks WHERE course_id=? AND content=? AND source_type=? AND source_doc=? AND COALESCE(page,-1)=COALESCE(?,-1) AND locator=? LIMIT 1',(cid,content,source_type,source_doc,page,locator)).fetchone()
    if old:
        con.commit();con.close();return {'ok':True,'id':old['id'],'duplicate':True}
    cur=con.execute('INSERT INTO user_marks(course_id,content,source_type,source_doc,page,locator,category,created_at) VALUES(?,?,?,?,?,?,?,?)',(cid,content,source_type,source_doc,page,locator,category,server.nowiso()))
    con.commit();mid=cur.lastrowid;con.close()
    return {'ok':True,'id':mid,'duplicate':False}

@app.delete('/api/p/{pid}/courses/{cid}/marks/{mid}')
def remove_mark(pid:int,cid:int,mid:int):
    server.course_row(pid,cid)
    con=server.db();ensure_marks(con)
    cur=con.execute('DELETE FROM user_marks WHERE id=? AND course_id=?',(mid,cid));con.commit();con.close()
    if not cur.rowcount: raise HTTPException(404,'표시한 내용을 찾지 못했어.')
    return {'ok':True}

@app.get('/api/p/{pid}/backup-v3')
def backup_v3(pid:int):
    p=server.profile_row(pid);con=server.db();ensure_marks(con)
    courses=[dict(x) for x in con.execute('SELECT * FROM courses WHERE profile_id=?',(pid,)).fetchall()]
    ids=[x['id'] for x in courses]
    data={'profile':{'id':p['id'],'name':p['name']},'courses':courses,'documents':[],'attempts':[],'card_reviews':[],'tutor_messages':[],'exam_patterns':[],'document_annotations':[],'user_marks':[],'format_version':3}
    for cid in ids:
        docs=[dict(x) for x in con.execute('SELECT id,course_id,name,pages,text_json,sha256,document_type,extraction_mode,image_count,created_at FROM documents WHERE course_id=?',(cid,)).fetchall()]
        data['documents']+=docs
        data['attempts'] += [dict(x) for x in con.execute('SELECT * FROM attempts WHERE course_id=?',(cid,)).fetchall()]
        data['card_reviews'] += [dict(x) for x in con.execute('SELECT * FROM card_reviews WHERE course_id=?',(cid,)).fetchall()]
        data['tutor_messages'] += [dict(x) for x in con.execute('SELECT * FROM tutor_messages WHERE course_id=?',(cid,)).fetchall()]
        data['exam_patterns'] += [dict(x) for x in con.execute('SELECT * FROM exam_patterns WHERE course_id=?',(cid,)).fetchall()]
        data['user_marks'] += [dict(x) for x in con.execute('SELECT * FROM user_marks WHERE course_id=?',(cid,)).fetchall()]
        for d in docs:
            data['document_annotations'] += [dict(x) for x in con.execute('SELECT document_id,page,data_json,updated_at FROM document_annotations WHERE document_id=?',(d['id'],)).fetchall()]
    con.commit();con.close()
    return JSONResponse(data,headers={'Content-Disposition':f'attachment; filename="forest_profile_{pid}_backup_v3.json"'})
