import os, tempfile, io, json
from pathlib import Path
os.environ['DATA_ROOT']=tempfile.mkdtemp(prefix='forest-test-')
os.environ['COOKIE_HTTPS_ONLY']='0'
os.environ.pop('OPENAI_API_KEY',None)
import fitz
from PIL import Image
from fastapi.testclient import TestClient
import server
import forest_app

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
 items=[{'type':'stroke','color':'#d6ff00','width':12,'opacity':.35,'points':[[.1,.2],[.4,.5]]},{'type':'text','color':'#17231e','size':24,'x':.2,'y':.3,'text':'중요'}]
 saved=c.put(base+f'/documents/{did}/annotations?page=1',json={'items':items})
 assert saved.status_code==200 and saved.json()['count']==2
 assert c.get(base+f'/documents/{did}/annotations?page=1').json()['items']==items
 assert c.get(base+f'/documents/{did}/file').content==original
 assert c.get(base+f'/documents/{did}/preview?page=2').status_code==400
 assert c.put(base+f'/documents/{did}/annotations?page=1',json={'items':[{'type':'text','color':'bad','size':24,'x':0,'y':0,'text':'x'}]}).status_code==400
 assert c.put(base+f'/documents/{did}/annotations?page=1',json={'items':[{'type':'stroke','color':'#d6ff00','width':12,'opacity':0,'points':[[.1,.2]]}]}).status_code==400
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
 assert (server.DATA_ROOT/'backups'/'before-9.2.0.sqlite3').exists()
 assert c.get(base).json()==before
 backup=c.get('/api/p/1/backup').json()
 assert backup['format_version']==5 and 'text_json' in backup['documents'][0] and 'exam_patterns' in backup and 'lecture_sessions' in backup
 assert c.get(base).headers['cache-control']=='no-store'
 assert c.get('/').status_code==200

def test_course_list_exposes_resume_summary_without_cross_profile_data():
 c=TestClient(server.app);cid=setup_course(c,'Resume Course');base=f'/api/p/1/courses/{cid}'
 c.post(base+'/documents',files={'files':('lecture.pdf',pdf_bytes(),'application/pdf')})
 assert c.post(base+'/analyze').status_code==200
 item=next(x for x in c.get('/api/p/1/courses').json() if x['id']==cid)
 assert item['document_count']==1 and item['due_count']>0 and item['last_score'] is None and item['analyzed']
 profiles=c.get('/api/profiles').json();existing=next((p for p in profiles if not p['is_owner']),None)
 if existing:guest=existing['id'];pin='1234'
 else:guest=c.post('/api/profiles',data={'name':'Resume Guest','pin':'6789'}).json()['id'];pin='6789'
 assert c.post(f'/api/profiles/{guest}/verify',data={'pin':pin}).status_code==200
 assert c.get('/api/p/1/courses').status_code==403
 assert c.get(f'/api/p/{guest}/courses').json()==[]

def test_exam_core_creates_focused_three_question_practice():
 c=TestClient(server.app);cid=setup_course(c,'Core Practice');base=f'/api/p/1/courses/{cid}'
 c.post(base+'/documents',files={'files':('core.pdf',pdf_bytes(),'application/pdf')})
 analysis=c.post(base+'/analyze').json();category=next(k for k in server.CORE_DETAIL_LABELS if analysis.get(k))
 result=c.post(base+'/core-practice',json={'category':category,'index':0})
 assert result.status_code==200,result.text
 data=result.json();assert len(data['questions'])==3 and data['focus']['category']==server.CORE_DETAIL_LABELS[category]
 assert all(q['source_doc']=='core.pdf' for q in data['questions'])

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

def test_lecture_api_audio_transcript_realtime_and_profile_isolation(monkeypatch):
 c=TestClient(server.app);cid=setup_course(c,'Lecture API');base=f'/api/p/1/courses/{cid}'
 created=c.post(base+'/lectures',json={'title':'Week 1'});assert created.status_code==200,created.text;sid=created.json()['id']
 assert c.get(base+'/lectures').json()['lectures'][0]['id']==sid
 first=c.post(base+f'/lectures/{sid}/transcript',json={'text':'시험에 꼭 나옵니다','start_seconds':2,'end_seconds':4,'client_event_id':'event-1'})
 assert first.status_code==200 and not first.json()['duplicate'];segment_id=first.json()['id']
 duplicate=c.post(base+f'/lectures/{sid}/transcript',json={'text':'시험에 꼭 나옵니다','client_event_id':'event-1'}).json()
 assert duplicate['id']==segment_id and duplicate['duplicate']
 assert c.patch(base+f'/lectures/{sid}/transcript/{segment_id}',json={'importance':'user'}).status_code==200
 assert c.post(base+f'/lectures/{sid}/classify-transcript',json={'text':'시험에 꼭 나옵니다'}).json()['importance']=='professor'
 audio=b'webm-audio-fixture-data';saved=c.post(base+f'/lectures/{sid}/audio',data={'duration_seconds':'12.5'},files={'audio':('lecture.webm',audio,'audio/webm')})
 assert saved.status_code==200,saved.text
 downloaded=c.get(base+f'/lectures/{sid}/audio');assert downloaded.status_code==200 and downloaded.content==audio
 note=c.post(base+f'/lectures/{sid}/finalize-note').json();assert '시험에 꼭 나옵니다' in note['text'] and note['user_count']==1
 monkeypatch.setattr(forest_app,'_openai_realtime_secret',lambda key,safety:{'value':'ek_test','expires_at':123})
 monkeypatch.setenv('OPENAI_API_KEY','sk-test')
 assert c.post(base+'/realtime-token').json()=={'value':'ek_test','expires_at':123}
 guest=next(p['id'] for p in c.get('/api/profiles').json() if not p['is_owner']);c.post(f'/api/profiles/{guest}/verify',data={'pin':'1234'})
 assert c.get(base+'/lectures').status_code==403

def test_recording_cancel_removes_draft_and_transcript_but_not_saved_recording():
 c=TestClient(server.app);cid=setup_course(c,'Cancel lecture');base=f'/api/p/1/courses/{cid}'
 created=c.post(base+'/lectures',json={'title':'Wrong recording'});sid=created.json()['id']
 assert c.post(base+f'/lectures/{sid}/transcript',json={'text':'버릴 자막','client_event_id':'cancel-1'}).status_code==200
 cancelled=c.delete(base+f'/lectures/{sid}');assert cancelled.status_code==200,cancelled.text
 assert all(x['id']!=sid for x in c.get(base+'/lectures').json()['lectures'])
 saved=c.post(base+'/lectures',json={'title':'Keep recording'}).json()['id']
 assert c.post(base+f'/lectures/{saved}/audio',data={'duration_seconds':'3'},files={'audio':('lecture.webm',b'valid-recording-audio','audio/webm')}).status_code==200
 assert c.delete(base+f'/lectures/{saved}').status_code==409
 saved_path=Path(forest_app.lecture_row(1,cid,saved)['audio_path']);assert saved_path.exists()
 assert c.delete(base+f'/lectures/{saved}?confirm_saved=true').status_code==200
 assert not saved_path.exists() and not c.get(base+'/lectures').json()['lectures']

def test_uploaded_recording_transcribes_and_builds_student_study_pack(monkeypatch):
 c=TestClient(server.app);cid=setup_course(c,'Uploaded Lecture');base=f'/api/p/1/courses/{cid}'
 uploaded=c.post(base+'/lectures/upload',data={'title':'Uploaded week 2','duration_seconds':'61'},files={'audio':('week2.mp3',b'long-enough-audio-fixture','audio/mpeg')})
 assert uploaded.status_code==200,uploaded.text;sid=uploaded.json()['id']
 monkeypatch.setattr(forest_app,'_transcribe_audio_file',lambda path:[
  {'start':0,'end':8,'text':'오늘 핵심은 수요 곡선의 이동입니다.','speaker':'교수','event':'batch:0'},
  {'start':8,'end':15,'text':'시험에 꼭 나오는 비교입니다.','speaker':'교수','event':'batch:1'},
 ])
 result=c.post(base+f'/lectures/{sid}/transcribe');assert result.status_code==202,result.text
 lecture=c.get(base+'/lectures').json()['lectures'][0]
 assert lecture['source_kind']=='uploaded' and lecture['transcript_status']=='ready' and lecture['transcript_count']==2
 transcript=c.get(base+f'/lectures/{sid}/transcript').json()['segments']
 assert transcript[0]['speaker']=='교수' and transcript[1]['importance']=='professor'
 monkeypatch.setattr(server,'json_call',lambda prompt,schema:None)
 pack=c.post(base+f'/lectures/{sid}/study-pack');assert pack.status_code==200,pack.text
 data=pack.json();assert len(data['questions'])>=1 and any(x['timestamp_seconds']==8 for x in data['key_points'])
 profile=c.get(base+'/learning-profile').json()
 assert profile['evidence']['lecture_count']>=1 and profile['recommendations']
