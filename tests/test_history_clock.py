from compass.config import Settings
from compass.rag import Answer, ChatService
from compass.storage import ChatStore
import pytest


@pytest.mark.parametrize('clock', ['same', 'backwards'])
def test_history_uses_transcript_order_despite_clock(tmp_path, monkeypatch, clock):
    store = ChatStore(tmp_path/'chat.sqlite3')
    cid = store.create()
    values = iter(['2026-01-02']*20 if clock == 'same' else [f'2026-01-{i:02}' for i in range(30, 10, -1)])
    monkeypatch.setattr('compass.storage.now', lambda: next(values))
    calls = []
    class Pipeline:
        manifest = {'dataset_version':'fixture', 'fingerprint':'fixture'}
        def answer(self, question, turns):
            calls.append([t['question'] for t in turns])
            return Answer('Fixture answer')
    service = ChatService(Settings(root=tmp_path), store, Pipeline)
    assert service.ask(cid, 'First').status == 'completed'
    assert service.ask(cid, 'Second').status == 'completed'
    assert calls == [[], ['First']]
