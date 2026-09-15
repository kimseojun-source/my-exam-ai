import os, tempfile, io, json
from pathlib import Path
os.environ['DATA_ROOT']=tempfile.mkdtemp(prefix='forest-test-')
os.environ['COOKIE_HTTPS_ONLY']='0'
os.environ.pop('OPENAI_API_KEY',None)
import fitz
from PIL import Image
from fastapi.testclient import TestClient
import server

def pdf_bytes(text='Economics studies supply and demand. Higher prices reduce quantity demanded, all else equal.'):
 d=fitz.open();p=d.new_page();p.insert_text((72,72),text);b=d.tobytes();d.close();return b

def image_bytes():
 b=io.BytesIO();Image.new('RGB',(100,100),'green').save(b,format='PNG');return b.getvalue()

def setup_course(client,name='Economics'):
 assert client.post('/api/profiles/1/verify',data={'pin':''}).status_code==200
 r=client.post('/api/p/1/courses',data={'name':name});assert r.status_code==200
 return r.json()['id']

def test_upload_partial_duplicate_original_and_isolation():
 c=TestClient(server.app);cid=setup_course(c);base=f'/api/p/1/courses/{cid}'
 r=c.post(base+'/documents',files=[('files',('lecture.pdf',pdf_bytes(),'application/pdf')),('files',('photo.png',image_bytes(),'image/png')),('files',('broken.pdf',b'bad','application/pdf'))])
 assert r.status_code==200,r.text
 data=r.json();assert len(data['added'])==2 and len(data['errors'])==1
 assert data['added'][1]['extraction']=='pending_vision'
 did=data['added'][1]['id']
 assert c.get(base+f'/documents/{did}/file').content==image_bytes()
 r=c.post(base+'/documents',files={'files':('photo.png',image_bytes(),'image/png')})
 assert len(r.json()['skipped'])==1
 assert c.post(base+f'/documents/{did}/reprocess').status_code==503
 other=setup_course(c,'Chemistry')
 assert c.get(f'/api/p/1/courses/{other}/documents/{did}/file').status_code==404
 guest=c.post('/api/profiles',data={'name':"Guest's <profile>",'pin':'1234'}).json()['id']
 assert c.post(f'/api/profiles/{guest}/verify',data={'pin':'1234'}).status_code==200
 assert c.get(base).status_code==403
 assert c.get(base+f'/documents/{did}/file').status_code==403
 assert TestClient(server.app).get(base).status_code==403

def test_document_preview_annotations_and_original_preserved():
 c=TestClient(server.app);cid=setup_course(c);base=f'/api/p/1/courses/{cid}'
 original=pdf_bytes();r=c.post(base+'/documents',files={'files':('write-on.pdf',original,'application/pdf')});did=r.json()['added'][0]['id']
 preview=c.get(base+f'/documents/{did}/preview?page=1')
 assert preview.status_code==200 and preview.headers['content-type']=='image/png' and preview.content.startswith(b'\x89PNG')
 items=[{'type':'stroke','color':'#ff0000','width':5,'points':[[.1,.2],[.4,.5]]},{'type':'text','color':'#17231e','size':24,'x':.2,'y':.3,'text':'중요'}]
 saved=c.put(base+f'/documents/{did}/annotations?page=1',json={'items':items})
 assert saved.status_code==200 and saved.json()['count']==2
 assert c.get(base+f'/documents/{did}/annotations?page=1').json()['items']==items
 assert c.get(base+f'/documents/{did}/file').content==original
 assert c.get(base+f'/documents/{did}/preview?page=2').status_code==400
 assert c.put(base+f'/documents/{did}/annotations?page=1',json={'items':[{'type':'text','color':'bad','size':24,'x':0,'y':0,'text':'x'}]}).status_code==400
 other=setup_course(c,'Other')
 assert c.get(f'/api/p/1/courses/{other}/documents/{did}/annotations?page=1').status_code==404

def test_analysis_and_tutor_receive_only_current_subject(monkeypatch):
 c=TestClient(server.app);cid=setup_course(c,'Physics');base=f'/api/p/1/courses/{cid}'
 c.post(base+'/documents',files={'files':('physics.pdf',pdf_bytes('PHYSICS_SENTINEL Force equals mass multiplied by acceleration. Newton describes the law of motion.'),'application/pdf')})
 other=setup_course(c,'Biology');c.post(f'/api/p/1/courses/{other}/documents',files={'files':('biology.pdf',pdf_bytes('BIOLOGY_SENTINEL Cells contain membranes and organelles. Photosynthesis converts light into energy.'),'application/pdf')})
 observed=[]
 def fake_json(prompt,schema,web=False):
  observed.append(prompt);return None
 monkeypatch.setattr(server,'json_call',fake_json)
 assert c.post(base+'/analyze').status_code==200
 assert 'PHYSICS_SENTINEL' in observed[0] and 'BIOLOGY_SENTINEL' not in observed[0]
 monkeypatch.setattr(server,'client',lambda:object())
 def fake_text(prompt,web=False):observed.append(prompt);return 'Force = mass × acceleration. physics.pdf p.1'
 monkeypatch.setattr(server,'text_call',fake_text)
 r=c.post(base+'/tutor',json={'question':'Explain force'})
 assert r.status_code==200 and r.json()['sources'][0]['doc']=='physics.pdf'
 assert 'BIOLOGY_SENTINEL' not in observed[-1]
 assert c.get(f'/api/p/1/courses/{other}').json()['tutor_history']==[]

def test_image_reprocess_and_empty_analysis(monkeypatch):
 c=TestClient(server.app);cid=setup_course(c);base=f'/api/p/1/courses/{cid}'
 r=c.post(base+'/documents',files={'files':('photo.png',image_bytes(),'image/png')});did=r.json()['added'][0]['id']
 assert c.post(base+'/analyze').status_code==400
 monkeypatch.setattr(server,'client',lambda:object())
 monkeypatch.setattr(server,'visual_image_notes',lambda path:[{'page':1,'text':'A short note.'}])
 assert c.post(base+f'/documents/{did}/reprocess').status_code==200
 assert server.chunks_from_docs(server.course_docs(1,cid))[0]['text']=='A short note.'

def test_backup_and_snapshot_preserve_existing_records():
 c=TestClient(server.app);cid=setup_course(c);base=f'/api/p/1/courses/{cid}'
 c.post(base+'/documents',files={'files':('lecture.pdf',pdf_bytes(),'application/pdf')})
 before=c.get(base).json();server.snapshot_existing_database()
 assert (server.DATA_ROOT/'backups'/'before-9.0.0.sqlite3').exists()
 assert c.get(base).json()==before
 backup=c.get('/api/p/1/backup').json()
 assert backup['format_version']==2 and 'text_json' in backup['documents'][0] and 'exam_patterns' in backup
 assert c.get(base).headers['cache-control']=='no-store'
 assert c.get('/').status_code==200

def test_vision_request_schema_and_rotation(monkeypatch):
 class Responses:
  def create(self,**kwargs):
   assert kwargs['input'][0]['content'][1]['type']=='input_image'
   assert kwargs['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,')
   return type('Result',(),{'output_text':json.dumps({'pages':[{'page':1,'text':'a visible note'}]})})()
 monkeypatch.setattr(server,'client',lambda:type('Client',(),{'responses':Responses()})())
 path=server.DATA_ROOT/'fixture.png';path.write_bytes(image_bytes())
 assert server.visual_image_notes(path)==[{'page':1,'text':'a visible note'}]

def test_visual_pdf_threshold_and_page_normalization():
 assert server.needs_visual_pdf(3,1.0,2)
 assert server.needs_visual_pdf(30,0.2,0)
 assert not server.needs_visual_pdf(20,1.0,2)
 pages=server.normalize_visual_pages([
  {'page':2,'text':'  supply   curve  '},
  {'page':'2','text':'supply curve'},
  {'page':2,'text':'equilibrium graph'},
  {'page':0,'text':'invalid'},
  {'page':99,'text':'invalid'},
  {'page':1,'text':''},
 ],3)
 assert pages==[{'page':2,'text':'supply curve\nequilibrium graph'}]
