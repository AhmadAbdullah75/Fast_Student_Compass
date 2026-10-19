"""Browser-test HTTP fixture. Never used by the normal application launcher."""
from pathlib import Path
import sys,tempfile,time
from threading import Lock
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from compass.config import Settings
from compass.storage import ChatStore
from compass.rag import ChatService,Answer
from compass.web import create_app

folder=PROJECT/'frontend/test-results'
folder.mkdir(exist_ok=True)
db=ChatStore(Path(tempfile.mkdtemp(prefix='server-',dir=folder))/'chats.sqlite3')
calls=[]
mutex=Lock()
reference={'id':'academic','title':'Academic Rules — test fixture','section':'Undergraduate rules',
    'pdf_page':10,'printed_label':'4','campus':'all','degree':'undergraduate','url':'https://www.nu.edu.pk/'}
citation={'id':'S1','chunk_id':'browser-fixture','excerpt':'Fixture passage: minimum degree duration is four academic years (8 regular semesters).','references':[reference]}

class Pipeline:
    manifest={'dataset_version':'browser-fixture','fingerprint':'fixture'}
    def answer(self,q,turns):
        with mutex:
            calls.append({'question':q,'history':[t['question'] for t in turns]})
            count=sum(c['question']==q for c in calls)
        time.sleep(4 if '[slow]' in q else .6)
        if '[quota]' in q and count==1:raise RuntimeError('429 quota key=SECRET')
        if '[timeout]' in q and count==1:raise TimeoutError('provider timeout SECRET')
        history=' · '.join(t['question'] for t in turns) or 'None'
        text=('A documented answer for your question. [S1]\n\n'
              '- The source contains the applicable rule.\n- Conditions and exceptions remain important.\n\n'
              '| Item | Requirement |\n|---|---|\n| Duration | Four years |\n\n'
              '$\\text{SGPA}=\\frac{\\sum P_i C_i}{\\sum C_i}$\n\n'
              f'Previous questions in this chat: {history}\n\n'
              'Literal code: `[S1]`\n\n<script>window.compassXss=true</script>')
        return Answer(text,[citation],diagnostics={'route':'document_rag','search_question':q,
            'history_context':history,'retrieved':[{'chunk_id':'browser-fixture','references':[reference],'passage':citation['excerpt']}]})

class Service(ChatService):
    def __init__(self,settings,storage):super().__init__(settings,storage,Pipeline)

old=db.create();tid=db.begin(old,'A saved question from earlier')
db.finish(tid,'An existing saved answer. [S1]',[citation],'fixture','browser-fixture',.1)
db.rename(old,'Earlier campus notes')
interrupted=db.create();db.begin(interrupted,'An interrupted saved question');db.rename(interrupted,'Interrupted conversation')
app=create_app(Settings(),db,Service)

@app.get('/api/test/calls')
def inspect_calls():return calls

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8502,log_level='warning')
