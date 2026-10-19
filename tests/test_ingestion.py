import json
from types import SimpleNamespace
import pytest
from compass.config import Settings
from compass.ingestion import audit, chunks, ingest, digest, write_json

def test_hidden_spread_content_is_not_attributed_to_visible_page():
    from compass.ingestion import extract_page
    class Page(dict):
        cropbox=SimpleNamespace(left=0,right=420,bottom=0,top=595)
        def extract_text(self,visitor_text):
            visitor_text('Hidden previous page', [1,0,0,1,0,0], [1,0,0,1,-376,500],None,10)
            visitor_text('Visible policy', [1,0,0,1,0,0], [1,0,0,1,40,500],None,10)
    assert extract_page(Page({'/Contents':True}))=='Visible policy'
    assert extract_page(Page())==''

@pytest.fixture
def dataset(tmp_path,monkeypatch):
    import compass.ingestion as module
    class Page:
        def extract_text(self,**kwargs):
            return 'Reviewed policy paragraph.\n\nAn exception must be preserved.'
    monkeypatch.setattr(module,'PdfReader',lambda path: SimpleNamespace(pages=[Page()],page_labels=['I']))
    settings=Settings(root=tmp_path,dimensions=3)
    folder=settings.data/'originals'; folder.mkdir(parents=True)
    sources=[]
    for i in range(4):
        content=f'fake reader input {i}'.encode()
        (folder/f'{i}.pdf').write_bytes(content)
        sources.append({'id':str(i),'filename':f'{i}.pdf','title':f'Source {i}',
            'reviewed_sha256':digest(content),'sections':[{'title':'Reviewed section',
                'pdf_start':1,'pdf_end':1,'campus':'all','degree':'undergraduate'}]})
    write_json(tmp_path/'sources.json',{'dataset_version':'test-v1','sources':sources})
    return settings

def test_audit_and_dedup_provenance(dataset):
    summary=audit(dataset)
    assert len(summary)==4 and all(r['page_count']==1 for r in summary)
    docs,version,config=chunks(dataset)
    assert len(docs)==1
    references=json.loads(docs[0].metadata['references'])
    assert len(references)==4
    assert all(r['pdf_page']==1 and r['pdf_page_index']==0 and r['printed_label']=='I' for r in references)

def test_review_hash_and_scope_gate(dataset):
    path=dataset.root/'sources.json'
    spec=json.loads(path.read_text())
    spec['sources'][0]['sections'][0]['degree']='postgraduate'
    write_json(path,spec)
    with pytest.raises(ValueError,match='undergraduate'):
        chunks(dataset)
    spec['sources'][0]['sections'][0]['degree']='undergraduate'
    spec['sources'][0]['reviewed_sha256']='wrong'
    write_json(path,spec)
    with pytest.raises(ValueError,match='reviewed_sha256'):
        chunks(dataset)

def test_persisted_chroma_and_unchanged_ingestion(dataset):
    class Embedding:
        calls=0
        def embed_documents(self,texts):
            self.calls+=len(texts)
            return [[1.,0.,0.] for _ in texts]
        def embed_query(self,text):
            return [1.,0.,0.]
    embedding=Embedding()
    first=ingest(dataset,embedding)
    assert first['status']=='indexed' and embedding.calls==1
    assert ingest(dataset,embedding)['status']=='unchanged' and embedding.calls==1
    from langchain_chroma import Chroma
    from chromadb.config import Settings as ChromaSettings
    store=Chroma(collection_name=first['collection'],embedding_function=embedding,
                 persist_directory=str(dataset.data/'chroma'),client_settings=ChromaSettings(anonymized_telemetry=False))
    assert len(store.max_marginal_relevance_search('policy',k=6,fetch_k=12,
        filter={'degree':{'$in':['all','undergraduate']}}))==1

def test_failed_index_does_not_publish_manifest(dataset):
    class Failing:
        def embed_documents(self,texts):
            raise RuntimeError('429 quota')
    with pytest.raises(RuntimeError):
        ingest(dataset,Failing())
    assert not (dataset.data/'manifest.json').exists()

def test_cross_page_rule_keeps_both_references(dataset,monkeypatch):
    import compass.ingestion as module
    class Page:
        def __init__(self,text): self.text=text
        def extract_text(self,**kwargs): return self.text
    monkeypatch.setattr(module,'PdfReader',lambda path: SimpleNamespace(pages=[
        Page('A student must pass the required courses'),Page('and have zero warnings. Exception: approval may be granted.')],page_labels=['1','2']))
    path=dataset.root/'sources.json'
    spec=json.loads(path.read_text())
    for source in spec['sources']: source['sections'][0]['pdf_end']=2
    write_json(path,spec)
    docs,_,_=chunks(dataset)
    assert len(docs)==1
    assert {r['pdf_page'] for r in json.loads(docs[0].metadata['references'])}=={1,2}
    assert 'Exception' in docs[0].page_content
