import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app import app
from backend.database import Base, Cookie, Task, User, get_db
from backend.routers.auth import get_current_user
from backend.routers.tasks import _normalize_profile_url
from backend.services.library_collector import collect_library
from backend.services.note_library import save_dataset
from backend.tasks.library_worker import run_collection
from tests.test_note_library import FakeCollector, raw, URL
from tests.test_library_analysis import sample_dataset, sample_output, CONFIG
from backend.services.library_analysis import build_bundle


class LibraryApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.engine=create_engine(f"sqlite:///{(self.root/'test.db').as_posix()}",connect_args={"check_same_thread":False})
        Base.metadata.create_all(self.engine)
        self.Session=sessionmaker(bind=self.engine)
        with self.Session() as s:
            s.add(User(id=1,username='test',password_hash='unused'))
            s.add(Cookie(id=1,user_id=1,cookie_json='web_session=test; a1=test'))
            s.commit()
        def db():
            with self.Session() as s:
                yield s
        app.dependency_overrides[get_db]=db
        app.dependency_overrides[get_current_user]=lambda:{'id':1,'username':'test'}
        self.client=TestClient(app)
        self.patches=[patch('backend.config.settings.data_dir',str(self.root)),patch('backend.tasks.worker._get_db_session',self.Session),patch('backend.tasks.library_worker._get_db_session',self.Session),patch('backend.tasks.library_worker.submit_collection',run_collection)]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_create_collect_export_and_access_control(self):
        def collect(url,cookies,checkpoint,**kwargs):
            return collect_library(url,cookies,checkpoint,collector=FakeCollector([{'notes':[raw(1),raw(2)],'has_more':False}]),delay=0)
        with patch('backend.tasks.library_worker.collect_library',collect):
            result=self.client.post('/api/library/',json={'profile_url':URL,'cookie_id':1})
        self.assertEqual(result.status_code,200,result.text)
        task_id=result.json()['id']
        dataset=self.client.get(f'/api/library/{task_id}').json()
        self.assertEqual(len(dataset['rows']),2)
        self.assertEqual(dataset['status'],'completed')
        self.assertFalse((self.root/'tasks'/str(task_id)/'results.json').exists())
        for format in ('xlsx','csv','feishu'):
            response=self.client.get(f'/api/library/{task_id}/export?format={format}&top=1')
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response.headers['content-disposition'])
            if format!='csv':
                self.assertEqual(load_workbook(io.BytesIO(response.content)).active.max_row,2)
        self.assertEqual(self.client.get(f'/api/library/{task_id}/export?format=exe').status_code,422)
        self.assertEqual(self.client.get(f'/api/library/{task_id}/export?top=-1').status_code,422)
        app.dependency_overrides[get_current_user]=lambda:{'id':999}
        self.assertEqual(self.client.get(f'/api/library/{task_id}').status_code,404)
        self.assertEqual(self.client.get(f'/api/library/{task_id}/export').status_code,404)

    def test_invalid_domain_path_and_cookie_owner(self):
        for url in ('https://xiaohongshu.com.evil/user/profile/testuser01','https://www.xiaohongshu.com/user/profile/foo/extra'):
            self.assertEqual(self.client.post('/api/library/',json={'profile_url':url,'cookie_id':1}).status_code,400)
        self.assertEqual(self.client.post('/api/library/',json={'profile_url':URL,'cookie_id':999}).status_code,400)

    def test_extension_entry_creates_collection_not_report(self):
        with patch('backend.tasks.library_worker.submit_collection') as submit:
            response=self.client.post('/api/extension/collect-current',json={'profile_url':URL,'cookie_text':'web_session=test; a1=test'})
        self.assertEqual(response.status_code,200,response.text)
        task_id=response.json()['task_id']
        submit.assert_called_once_with(task_id)
        with self.Session() as s:
            self.assertEqual(s.get(Task,task_id).task_type,'note_collection')
        self.assertIn('%2Flibrary',response.json()['report_url'])

    def test_ai_delivery_end_to_end_and_approval_gate(self):
        dataset = sample_dataset()
        with self.Session() as s:
            s.add(Task(id=100, user_id=1, task_type='note_collection', status='completed'))
            s.commit()
        root = self.root / 'tasks' / '100'
        root.mkdir(parents=True)
        (root / 'dataset.json').write_text(__import__('json').dumps(dataset), encoding='utf-8')
        url = '/api/library/100/analysis'
        self.assertEqual(self.client.post(url, json={'goal':'计划三个实际选题'}).status_code, 400)
        self.assertEqual(self.client.post(url, json={'goal':'短', 'consent':True}).status_code, 422)
        output = sample_output(build_bundle(dataset, '计划三个实际选题'))
        with patch('backend.routers.library.ai_config_status', return_value=CONFIG), \
             patch('backend.services.library_analysis.generate_json', return_value=(output, {'output_tokens':100})), \
             patch('backend.tasks.analysis_worker._pool.submit', side_effect=lambda fn,*args: fn(*args)):
            response = self.client.post(url, json={'goal':'计划三个实际选题', 'consent':True})
            self.assertEqual(response.status_code, 202, response.text)
            state = self.client.get(url).json()
        self.assertEqual(state['status'], 'ready', state)
        self.assertNotIn('secret-key', str(state))
        self.assertEqual(self.client.get(url+'/export').status_code, 409)
        preview = self.client.get(url+'/export?preview=true')
        self.assertEqual(preview.status_code, 200)
        self.assertIn('待人工复核', preview.text)
        self.assertEqual(self.client.post(url+'/approve', json={'run_id':state['run_id']}).status_code, 400)
        self.assertEqual(self.client.post(url+'/approve', json={'run_id':'wrong','confirmed':True}).status_code, 409)
        response = self.client.post(url+'/approve', json={'run_id':state['run_id'], 'confirmed':True})
        self.assertEqual(response.status_code, 200, response.text)
        export = self.client.get(url+'/export')
        self.assertEqual(export.status_code, 200)
        self.assertIn('交付前已人工确认', export.text)
        self.assertNotIn('must-not-leak', export.text)
        app.dependency_overrides[get_current_user]=lambda:{'id':999}
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url+'/export').status_code, 404)
        self.assertEqual(self.client.post(url+'/approve', json={'run_id':state['run_id'], 'confirmed':True}).status_code, 404)
        app.dependency_overrides[get_current_user]=lambda:{'id':1}
        dataset['rows'][0]['liked_count']=99999
        (root / 'dataset.json').write_text(__import__('json').dumps(dataset), encoding='utf-8')
        self.assertEqual(self.client.get(url).json()['status'], 'stale')
        self.assertEqual(self.client.get(url+'/export').status_code, 409)

    def test_llm_settings_validate_url_and_never_return_key_fragments(self):
        endpoint = '/api/settings/llm'
        invalid = self.client.post(endpoint, json={
            'llm_provider': 'custom',
            'llm_api_url': 'http://remote.example/v1',
            'llm_model': 'test-model',
            'llm_api_key': 'private-key-123456789',
        })
        self.assertEqual(invalid.status_code, 400)
        invalid_provider = self.client.post(endpoint, json={'llm_provider': 'unknown'})
        self.assertEqual(invalid_provider.status_code, 422)
        valid = self.client.post(endpoint, json={
            'llm_provider': 'custom',
            'llm_api_url': 'https://model.example/v1',
            'llm_model': 'test-model',
            'llm_api_key': 'private-key-123456789',
        })
        self.assertEqual(valid.status_code, 200, valid.text)
        response = self.client.get(endpoint)
        self.assertTrue(response.json()['has_key'])
        self.assertNotIn('private-key', response.text)
        self.assertNotIn('123456789', response.text)
