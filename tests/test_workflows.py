"""Actual Streamlit widgets and SQLite, deterministic model double, no API cost."""
from pathlib import Path
import json
from streamlit.testing.v1 import AppTest
from compass.config import Settings
from compass.storage import ChatStore
from compass.rag import ChatService, Answer

def test_retry_resume_isolation_and_trace_ui(tmp_path,monkeypatch):
    import compass.config
    import compass.rag
    monkeypatch.setattr(compass.config,'Settings',lambda:Settings(root=tmp_path))
    monkeypatch.setenv('GOOGLE_API_KEY','offline-ui-test')
    (tmp_path/'data').mkdir()
    (tmp_path/'data/manifest.json').write_text(json.dumps({'dataset_version':'ui-fixture'}))
    calls=[]
    class Pipeline:
        manifest={'dataset_version':'ui-fixture','fingerprint':'ui-fixture'}
        def answer(self,q,turns):
            calls.append((q,[t['question'] for t in turns]))
            if len(calls)==1: raise RuntimeError('429 quota')
            return Answer('A source-backed fixture answer [S1]',[{'id':'S1','excerpt':'Fixture passage',
                'references':[{'title':'Fixture','section':'Section','pdf_page':1,'printed_label':'1',
                    'campus':'all','degree':'undergraduate'}]}],diagnostics={
                    'route':'document_rag','search_question':'Standalone fixture question',
                    'history_context':'Fixture active context','retrieved':[], 'packed_source_ids':{}})
    class Service(ChatService):
        def __init__(self,settings,storage):super().__init__(settings,storage,Pipeline)
    monkeypatch.setattr(compass.rag,'ChatService',Service)
    script=str(Path(__file__).parents[1]/'app.py')
    app=AppTest.from_file(script,default_timeout=30).run()
    first=app.session_state.chat_id
    app.chat_input[0].set_value('First question').run()
    assert not app.exception and app.chat_input[0].disabled
    assert any('quota' in a.value for a in app.warning)
    next(b for b in app.button if b.label=='Retry').click().run()
    assert not app.exception and not app.chat_input[0].disabled
    db=ChatStore(tmp_path/'data/chats.sqlite3')
    assert len(db.turns(first))==1 and db.turns(first)[0]['status']=='completed'
    next(c for c in app.checkbox if c.label=='Show retrieval details').check().run()
    assert not app.exception
    assert any('Standalone fixture question' in m.value for m in app.markdown)
    restarted=AppTest.from_file(script,default_timeout=30).run()
    restarted.chat_input[0].set_value('Follow-up after restart').run()
    assert calls[-1][1]==['First question']
    next(b for b in restarted.button if 'New chat' in b.label).click().run()
    second=restarted.session_state.chat_id
    assert first!=second
    restarted.chat_input[0].set_value('Separate chat question').run()
    assert calls[-1][1]==[]
    assert len(db.turns(first))==2 and len(db.turns(second))==1
    assert not restarted.exception
    restarted.selectbox[0].set_value(first).run()
    assert not restarted.exception and restarted.session_state.chat_id==first
    assert len(restarted.chat_message)==4
    assert not any('Separate chat question' in m.value for m in restarted.markdown)
