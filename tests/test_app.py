from pathlib import Path
from streamlit.testing.v1 import AppTest

def test_empty_app_and_saved_chat_controls(tmp_path,monkeypatch):
    import compass.config
    from compass.config import Settings
    monkeypatch.setattr(compass.config,'Settings',lambda: Settings(root=tmp_path))
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=30).run()
    assert not app.exception
    assert app.chat_input[0].disabled
    assert any('Setup required' in w.value for w in app.warning)
    new=next(b for b in app.button if 'New chat' in b.label)
    new.click().run()
    assert not app.exception
    assert len(app.selectbox[0].options)==2

def test_question_resume_rename_and_delete(tmp_path,monkeypatch):
    import compass.config
    import compass.rag
    from compass.config import Settings
    from compass.storage import ChatStore
    from compass.rag import ChatService, Answer
    import json
    class Pipeline:
        manifest={'dataset_version':'test','fingerprint':'123'}
        def answer(self,question,turns):
            return Answer('A supported answer [S1]',[{'id':'S1','excerpt':'Policy passage',
                'references':[{'title':'Test source','section':'Rules','pdf_page':2,'printed_label':'1',
                               'campus':'all','degree':'undergraduate'}]}])
    class Service(ChatService):
        def __init__(self,settings,storage):
            super().__init__(settings,storage,Pipeline)
    monkeypatch.setattr(compass.config,'Settings',lambda: Settings(root=tmp_path))
    monkeypatch.setattr(compass.rag,'ChatService',Service)
    monkeypatch.setenv('GOOGLE_API_KEY','test-placeholder-no-network')
    (tmp_path/'data').mkdir()
    (tmp_path/'data/manifest.json').write_text(json.dumps({'dataset_version':'test'}))
    script=str(Path(__file__).parents[1]/'app.py')
    app=AppTest.from_file(script,default_timeout=30).run()
    app.chat_input[0].set_value('How does registration work?').run()
    assert not app.exception and len(app.chat_message)==2
    assert any('A supported answer' in text.value for text in app.markdown)
    app.text_input[0].set_value('Registration notes')
    next(b for b in app.button if b.label=='Rename').click().run()
    assert not app.exception
    restarted=AppTest.from_file(script,default_timeout=30).run()
    assert len(restarted.chat_message)==2
    assert restarted.text_input[0].value=='Registration notes'
    restarted.checkbox[0].check().run()
    next(b for b in restarted.button if b.label=='Delete').click().run()
    assert not restarted.exception
    assert not restarted.chat_message
