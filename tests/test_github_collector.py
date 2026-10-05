import base64
import json
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from app.acquisition.common import ProbeError
from app.collectors.bundle import read_json, private_write, digest
from app.collectors.github import GitHubConfig, Preparation, make_item, validate_bundle, PARSER, FILTER
from app.collectors.github_reader import RepositoryReader, Paused
from app.collectors.client import apply_bundle
from app.importers.canonical import GitHubCommitPayload
from app.schemas.collection_run import GitHubCollectorItem, GitHubRunCreate
from app.models.entry import Entry
from app.models.history import EntryVersion

SHA = 'a'*40
TREE = 'b'*40
BLOB = 'c'*40


class Reader:
    """A deterministic paginated GitHub source, with no real network calls."""
    def __init__(self, commits=1, files=1):
        self.commits, self.files, self.calls = commits, files, []
        self.pause = None
    def next_page(self, headers, expected):
        return headers.get('next')
    def get(self, path):
        self.calls.append(path)
        if self.pause and self.pause in path:
            self.pause = None
            raise Paused('RATE_LIMIT', 1)
        url = urlsplit(path)
        endpoint = url.path.removeprefix('/repos/example/repo')
        page = int(parse_qs(url.query).get('page', ['1'])[0])
        if not endpoint:
            return {'id':123}, {}
        if endpoint == '/branches':
            return [{'name':'main'}], {}
        if endpoint.startswith('/branches/'):
            return {'commit':{'sha':SHA}}, {}
        if endpoint == '/commits':
            shas = [SHA] + [f'{i:040x}' for i in range(1,self.commits)]
            rows = shas[(page-1)*100:page*100]
            return [{'sha':s} for s in rows], {'next':page+1} if page*100 < len(shas) else {}
        if endpoint.startswith('/commits/'):
            sha = endpoint.split('/')[-1]
            files = [{'filename':'README.md' if i==0 else f'file-{i}.txt', 'status':'modified', 'patch':'+recorded change', 'additions':1} for i in range(self.files)]
            return {'sha':sha, 'commit':{'tree':{'sha':TREE}, 'message':'Improve historical collection',
                'author':None, 'committer':{'name':'Synthetic author','date':'2026-01-01T00:00:00Z'}},
                'parents':[], 'files':files[(page-1)*100:page*100]}, {'next':page+1} if page*100 < len(files) else {}
        if endpoint.startswith('/git/trees/'):
            return {'tree':[{'path':'README.md','mode':'100644','sha':BLOB}], 'truncated':False}, {}
        if endpoint.startswith('/contents/'):
            return {'type':'file','encoding':'base64','sha':BLOB,'size':18,
                'content':base64.b64encode(b'Historical README.').decode()}, {}
        raise AssertionError(path)


def prepared(tmp_path, reader=None, **config):
    cfg = GitHubConfig(repository='example/repo', repository_id=123, **config)
    prep = Preparation(tmp_path, cfg, reader or Reader())
    prep.run()
    manifest = prep.seal()
    return cfg, manifest


def create_data(manifest):
    return {key:manifest[key] for key in ('client_run_uuid','provider','scope','manifest_digest','parser_version','filter_version','expected_items','coverage')}


def test_paginated_walk_and_files_multiple_branches(tmp_path):
    reader = Reader(commits=102, files=301)
    cfg, manifest = prepared(tmp_path, reader, branches=['main','secondary'])
    assert manifest['coverage']['commits'] == 102
    assert manifest['coverage']['documents'] == 102
    assert manifest['expected_items'] == 204
    assert all(b['walk_complete'] and b['commits']==102 for b in manifest['coverage']['branches'])
    assert len(manifest['coverage']['head_documents']) == 1
    item = next(read_json(tmp_path/r['file'], cfg.turn_bytes) for r in manifest['items'] if ':commit:' in r['external_id'])
    assert len(item['payload']['files']) == 301
    assert item['payload']['author']['name'] == ''
    validate_bundle(tmp_path,cfg)


def test_resume_pins_head_and_no_duplicate_journal(tmp_path):
    cfg = GitHubConfig(repository='example/repo',repository_id=123)
    reader = Reader()
    reader.pause = '/contents/'
    prep = Preparation(tmp_path,cfg,reader)
    with pytest.raises(Paused):
        prep.run()
    assert prep.state['branches'][0]['head_sha'] == SHA
    resumed = Preparation(tmp_path,cfg,reader)
    resumed.run()
    assert reader.calls.count('/repos/example/repo/branches/main') == 1
    assert len(resumed.state['items']) == 2
    assert len(resumed.state['documents']) == 1
    manifest = resumed.seal()
    assert len(manifest['coverage']['head_documents']) == 1
    with pytest.raises(FileExistsError):
        resumed.seal()


def test_incomplete_seal_integrity_and_body_free_failure(tmp_path):
    cfg = GitHubConfig(repository='example/repo',repository_id=123)
    prep = Preparation(tmp_path,cfg,Reader())
    with pytest.raises(ProbeError,match='incomplete'):
        prep.seal()
    prep.invalid(f'repo:123:commit:{SHA}','INVALID_ITEM')
    manifest = prep.seal(partial=True)
    assert manifest['coverage']['lower_bound']
    validate_bundle(tmp_path,cfg)
    manifest['coverage']['repository_id']=124
    private_write(tmp_path/'manifest.json',manifest,replace=True)
    with pytest.raises(ProbeError,match='integrity'):
        validate_bundle(tmp_path,cfg)


@pytest.mark.parametrize('mode',['120000','160000'])
def test_symlink_submodule_not_followed(tmp_path,mode):
    reader = Reader()
    original = reader.get
    def get(path):
        body,headers = original(path)
        if '/git/trees/' in path:
            body['tree'][0]['mode']=mode
        return body,headers
    reader.get = get
    cfg, manifest = prepared(tmp_path,reader)
    assert manifest['coverage']['documents']==0
    assert 'DOCUMENT_TYPE_OMITTED' in manifest['coverage']['gaps']
    assert not any('/contents/' in p for p in reader.calls)


def test_deleted_document_and_missing_patch_are_explicit(tmp_path):
    reader=Reader()
    original=reader.get
    def get(path):
        body,headers=original(path)
        if '/commits/' in path:
            body['files'][0].update(status='removed',patch=None)
        return body,headers
    reader.get=get
    cfg,manifest=prepared(tmp_path,reader)
    # This synthetic tree still contains README at head, so baseline is appropriate.
    document=next(read_json(tmp_path/r['file'],cfg.turn_bytes) for r in manifest['items'] if ':document:' in r['external_id'])
    assert document['payload']['snapshot_reason']=='head_baseline'
    assert 'PATCH_UNAVAILABLE' in manifest['coverage']['gaps']


def test_reader_cache_budget_scope_and_link_validation(tmp_path):
    cfg=GitHubConfig(repository='example/repo',repository_id=123,max_requests=1)
    reader=RepositoryReader(tmp_path,cfg,token='never-persist-this')
    class Response:
        headers={'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'9999999999'}
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,n): return b'{"id":123}'
    class Opener:
        def open(self,*args,**kwargs): return Response()
    reader.opener=Opener()
    path='/repos/example/repo'
    assert reader.get(path)[0]['id']==123
    assert reader.get(path)[0]['id']==123  # Cached reads survive quota pause.
    with pytest.raises(Paused,match='RATE_LIMIT'): reader.get(path+'/branches')
    assert 'never-persist-this' not in ''.join(p.read_text() for p in tmp_path.iterdir())
    with pytest.raises(ProbeError): reader.get('/repos/example/repository')
    expected=path+'/commits?sha='+SHA+'&per_page=100&page=1'
    good='https://api.github.com'+expected.replace('&page=1','&page=2')
    assert reader.next_page({'link':f'<{good}>; rel="next"'},expected)==2
    for link in [good.replace('api.github.com','evil.example'),good.replace('sha='+SHA+'&',''),good+'&extra=1']:
        with pytest.raises(Paused): reader.next_page({'link':f'<{link}>; rel="next"'},expected)


def test_github_run_replay_evidence_search_and_owner(client,auth_headers,db_session,another_user,tmp_path):
    from app.security import create_access_token
    cfg,manifest=prepared(tmp_path)
    data=create_data(manifest)
    response=client.post('/collection-runs',headers=auth_headers,json=data)
    assert response.status_code==200,response.text
    run=response.json()
    for row in manifest['items']:
        item=read_json(tmp_path/row['file'],cfg.turn_bytes)
        sent=client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=item)
        assert sent.status_code==200,sent.text
        assert sent.json()['outcome']=='new'
        assert client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=item).json()==sent.json()
    assert client.post(f"/collection-runs/{run['id']}/finish",headers=auth_headers).json()['status']=='completed'
    assert client.get('/collection-runs?provider=github',headers=auth_headers).json()[0]['coverage']['documents']==1
    assert client.get('/collection-runs',headers=auth_headers).json()==[]
    assert db_session.scalar(select(func.count()).select_from(EntryVersion))==2
    entries=list(db_session.scalars(select(Entry)))
    for entry in entries:
        response=client.get(f'/entries/{entry.id}/github-presentation',headers=auth_headers)
        assert response.status_code==200,response.text
        assert response.json()['related'][0]['id'] != entry.id
        assert response.json()['locator'].startswith('https://github.com/example/repo/')
        other={'Authorization':'Bearer '+create_access_token(another_user.id)}
        assert client.get(f'/entries/{entry.id}/github-presentation',headers=other).status_code==404
        assert not entry.external_ai_allowed
    search=client.get('/entries/search',headers=auth_headers,params={'q':'Historical README','source':'github'})
    assert search.status_code==200
    assert search.json()['total']==1
    row=manifest['items'][0]
    item=read_json(tmp_path/row['file'],cfg.turn_bytes)
    target=next(e for e in entries if e.external_id==item['external_id'])
    client.delete(f'/entries/{target.id}',headers=auth_headers)
    assert client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=item).json()['error_code']=='REIMPORT_BLOCKED'


def test_provider_scope_contracts_reject_before_storing(client,auth_headers,tmp_path):
    cfg,manifest=prepared(tmp_path)
    data=create_data(manifest)
    for change in [{'scope':'repo:124'},{'provider':'unknown'},{'coverage':{**data['coverage'],'expected_items':2}},{'coverage':{**data['coverage'],'gaps':['MADE_UP']}}]:
        assert client.post('/collection-runs',headers=auth_headers,json={**data,**change}).status_code==422
    run=client.post('/collection-runs',headers=auth_headers,json=data).json()
    bad=f'repo:124:commit:{SHA}'
    assert client.get(f"/collection-runs/{run['id']}/preflight",headers=auth_headers,params={'external_id':bad}).status_code==422
    assert client.post(f"/collection-runs/{run['id']}/outcomes",headers=auth_headers,json={'external_id':bad,'payload_digest':'a'*64,'error_code':'INVALID_ITEM'}).status_code==422
    item=read_json(tmp_path/manifest['items'][0]['file'],cfg.turn_bytes)
    item['payload']['repository_id']=124
    assert client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=item).status_code==422


def test_real_http_apply_and_replay(tmp_path,client,auth_headers,db_session):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from threading import Thread
    cfg,manifest=prepared(tmp_path)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self): self.forward()
        def do_POST(self): self.forward()
        def forward(self):
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            result=client.request(self.command,self.path,content=body,headers=dict(self.headers))
            self.send_response(result.status_code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(result.content)))
            self.end_headers()
            self.wfile.write(result.content)
    server=HTTPServer(('127.0.0.1',0),Handler)
    worker=Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        options=dict(validator=validate_bundle,item_type=GitHubCollectorItem,run_type=GitHubRunCreate,password='test-password')
        url=f'http://127.0.0.1:{server.server_port}'
        result=apply_bundle(tmp_path,cfg,url,'test@example.com',**options)
        assert result['counts']=={'new':2}
        assert apply_bundle(tmp_path,cfg,url,'test@example.com',**options)['id']==result['id']
        assert db_session.scalar(select(func.count()).select_from(Entry))==2
        assert db_session.scalar(select(func.count()).select_from(EntryVersion))==2
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


def test_numeric_repository_links_are_checked_against_selected_id(tmp_path):
    cfg=GitHubConfig(repository='example/repo',repository_id=123)
    reader=RepositoryReader(tmp_path,cfg)
    expected='/repos/example/repo/commits?sha='+SHA+'&page=1&per_page=100'
    numeric='https://api.github.com/repositories/123/commits?sha='+SHA+'&page=2&per_page=100'
    assert reader.next_page({'link':f'<{numeric}>; rel="next"'},expected)==2
    with pytest.raises(Paused):
        reader.next_page({'link':f'<{numeric.replace("repositories/123", "repositories/124")}>; rel="next"'},expected)


@pytest.mark.parametrize('status,headers,code',[(401,{},'AUTH_FAILED'),(403,{},'ACCESS_DENIED'),(404,{},'REF_UNAVAILABLE'),(409,{},'CONFLICT'),(302,{},'REPOSITORY_REDIRECT'),(429,{'Retry-After':'90'},'RATE_LIMIT'),(403,{'X-RateLimit-Remaining':'0','X-RateLimit-Reset':'9999999999'},'RATE_LIMIT')])
def test_reader_http_failures_are_bounded_and_never_redirect(tmp_path,status,headers,code):
    import urllib.error
    from email.message import Message
    cfg=GitHubConfig(repository='example/repo',repository_id=123)
    reader=RepositoryReader(tmp_path,cfg)
    info=Message()
    for k,v in headers.items(): info[k]=v
    class Opener:
        def open(self,*args,**kwargs): raise urllib.error.HTTPError('https://api.github.com',status,'untrusted body',info,None)
    reader.opener=Opener()
    with pytest.raises(Paused,match=code) as raised: reader.get('/repos/example/repo')
    assert reader.requests==1
    if code=='RATE_LIMIT': assert raised.value.retry_at>0


def test_nested_globs_and_invalid_document_outcome(tmp_path):
    reader=Reader()
    original=reader.get
    nested='d'*40
    leaf='e'*40
    def get(path):
        if '/git/trees/' in path:
            sha=path.split('/')[-1]
            row=({'path':'docs','mode':'040000','sha':nested} if sha==TREE else {'path':'nested','mode':'040000','sha':leaf} if sha==nested else {'path':'guide.md','mode':'100644','sha':BLOB})
            return {'tree':[row],'truncated':False},{}
        body,headers=original(path)
        if '/contents/' in path: body['content']=base64.b64encode(b'\xffinvalid utf8').decode()
        return body,headers
    reader.get=get
    cfg,manifest=prepared(tmp_path,reader,documents=['docs/**/*.md'])
    assert 'DOCUMENT_INVALID' in manifest['coverage']['gaps']
    assert any(r['error_code']=='INVALID_ITEM' and r['file'] is None for r in manifest['items'])
    validate_bundle(tmp_path,cfg)


def test_cleanup_refuses_unrelated_files_and_keeps_config(tmp_path):
    from app.collectors.github import cleanup
    cfg,manifest=prepared(tmp_path)
    (tmp_path/'unrelated.txt').write_text('Keep me')
    with pytest.raises(ProbeError,match='unknown'): cleanup(tmp_path,cfg)
    assert (tmp_path/'manifest.json').exists()
    (tmp_path/'unrelated.txt').unlink()
    assert cleanup(tmp_path,cfg)>0
    assert list(p.name for p in tmp_path.iterdir())==['.apply.lock']


def test_api_file_cap_marks_partial_without_unbounded_payload(tmp_path):
    cfg,manifest=prepared(tmp_path,Reader(files=3000))
    row=next(r for r in manifest['items'] if ':commit:' in r['external_id'])
    item=read_json(tmp_path/row['file'],cfg.turn_bytes)
    assert 'FILE_PAGE_LIMIT' in item['payload']['omissions']
    assert item['completeness']=='partial'
    assert manifest['coverage']['lower_bound']


def test_document_wire_overhead_is_a_failure_not_silent_truncation(tmp_path):
    reader=Reader()
    original=reader.get
    def get(path):
        body,headers=original(path)
        if '/contents/' in path:
            raw=b'x'*1048576
            body.update(size=len(raw),content=base64.b64encode(raw).decode())
        return body,headers
    reader.get=get
    cfg,manifest=prepared(tmp_path,reader)
    rows=[r for r in manifest['items'] if ':document:' in r['external_id']]
    assert len(rows)==1 and rows[0]['file'] is None and rows[0]['error_code']=='INVALID_ITEM'
    assert manifest['coverage']['documents']==0
    validate_bundle(tmp_path,cfg)


def test_lower_bound_counts_prevent_completed_status(client,auth_headers,tmp_path):
    cfg,manifest=prepared(tmp_path)
    data=create_data(manifest)
    data['coverage']['lower_bound']=True
    run=client.post('/collection-runs',headers=auth_headers,json=data).json()
    for row in manifest['items']:
        item=read_json(tmp_path/row['file'],cfg.turn_bytes)
        assert client.post(f"/collection-runs/{run['id']}/items",headers=auth_headers,json=item).status_code==200
    assert client.post(f"/collection-runs/{run['id']}/finish",headers=auth_headers).json()['status']=='partial'


def test_synthetic_demo_command_creates_connected_readonly_records(client,auth_headers,db_session,monkeypatch,capsys):
    from scripts import seed_github_demo
    class API:
        def __init__(self,url): pass
        def login(self,email,password): return 1
        def request(self,path,data=None):
            result=client.request('POST' if data is not None else 'GET',path,headers=auth_headers,json=data)
            assert result.status_code==200,result.text
            return result.json()
    monkeypatch.setattr(seed_github_demo,'CollectorAPI',API)
    monkeypatch.setattr(seed_github_demo.getpass,'getpass',lambda prompt:'synthetic password')
    monkeypatch.setattr('sys.argv',['seed_github_demo.py','--email','test@example.com'])
    seed_github_demo.main()
    assert 'two synthetic records' in capsys.readouterr().out
    entries=list(db_session.scalars(select(Entry)))
    assert len(entries)==2
    assert all(e.read_only and not e.external_ai_allowed for e in entries)
    assert client.get(f'/entries/{entries[0].id}/github-presentation',headers=auth_headers).json()['related'][0]['id']==entries[1].id


def test_empty_patch_is_distinct_from_unavailable(tmp_path):
    from app.importers.normalizer import EntryNormalizer
    reader=Reader()
    original=reader.get
    def get(path):
        body,headers=original(path)
        if '/commits/' in path: body['files'][0]['patch']=''
        return body,headers
    reader.get=get
    cfg,manifest=prepared(tmp_path,reader)
    row=next(r for r in manifest['items'] if ':commit:' in r['external_id'])
    item=GitHubCollectorItem.model_validate(read_json(tmp_path/row['file'],cfg.turn_bytes))
    assert item.payload.files[0].patch_state=='available'
    assert '[Patch unavailable]' not in EntryNormalizer().normalize(item).content


def test_cli_auth_token_stays_in_memory_and_failure_is_sanitized(monkeypatch):
    from app.collectors.github import github_token
    from types import SimpleNamespace
    monkeypatch.setattr('app.collectors.github.subprocess.run',lambda *args,**kwargs:SimpleNamespace(returncode=0,stdout='synthetic-secret\n',stderr=''))
    assert github_token(True)=='synthetic-secret'
    monkeypatch.setattr('app.collectors.github.subprocess.run',lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout='',stderr='synthetic-secret private diagnostic'))
    with pytest.raises(ProbeError,match='authentication unavailable') as error:
        github_token(True)
    assert 'synthetic-secret' not in str(error.value)


def test_signed_in_resume_uses_its_own_rate_bucket(tmp_path):
    cfg=GitHubConfig(repository='example/repo',repository_id=123)
    reader=Reader()
    prep=Preparation(tmp_path,cfg,reader)
    prep.state['retry_at']=9999999999
    prep.save()
    assert Preparation(tmp_path,cfg,Reader()).reader.retry_at==9999999999
    signed=Reader()
    signed.authenticated=True
    resumed=Preparation(tmp_path,cfg,signed)
    assert resumed.reader.retry_at==0
    resumed.state['retry_at']=9999999999
    resumed.save()
    assert Preparation(tmp_path,cfg,signed).reader.retry_at==9999999999
