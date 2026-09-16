import json
from fastapi import HTTPException, Request
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

@app.get('/api/p/{pid}/courses/{cid}/marks')
def marks(pid:int,cid:int):
    server.course_row(pid,cid)
    con=server.db();ensure_marks(con)
    rows=con.execute('SELECT * FROM user_marks WHERE course_id=? ORDER BY id DESC',(cid,)).fetchall()
    con.commit();con.close()
    return {'marks':[dict(r) for r in rows],'count':len(rows)}

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
