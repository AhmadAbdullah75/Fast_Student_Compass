import json
from pathlib import Path
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from compass.config import Settings
from compass.rag import RagPipeline

TURNS=json.loads((Path(__file__).parent/'fixtures/repair-sgpa-followup.json').read_text(encoding='utf-8'))['turns']

def test_recorded_grade_definition_correction_uses_calculation_guard(tmp_path):
    row=TURNS[1];trace=row['diagnostics']
    docs=[Document(page_content=d['passage'],metadata={'chunk_id':d['chunk_id'],'references':json.dumps(d['references'])}) for d in trace['retrieved']]
    class Store:
        def as_retriever(self,**kw):return RunnableLambda(lambda _:docs)
    calls=[]
    def model(*args,**kwargs):
        calls.append(1)
        return json.dumps(trace['interpretation']) if len(calls)==1 else trace['raw_answer']
    result=RagPipeline(Settings(root=tmp_path),Store(),RunnableLambda(model)).answer(row['question'],TURNS[:1])
    assert 'conflict' in result.answer.lower()
    assert result.diagnostics['route']=='clarification'
    assert len(calls)==1
