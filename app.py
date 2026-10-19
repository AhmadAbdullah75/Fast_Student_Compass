import os
import streamlit as st
from compass.config import Settings
from compass.storage import ChatStore
from compass.rag import ChatService
from compass.ingestion import read_json

st.set_page_config(page_title='CFD Student Compass', page_icon='🧭', layout='centered')
settings = Settings()
store = ChatStore(settings.data / 'chats.sqlite3')
service = ChatService(settings, store)

st.title('🧭 CFD Student Compass')
st.caption('An undergraduate guide to FAST policies, campus services, and financial assistance.')
st.info('Student-built reference project. University offices retain final authority; documents may not reflect the latest policy.')

with st.sidebar:
    st.header('Your conversations')
    st.caption('One local workspace • saved on this laptop')
    if st.button('＋ New chat', width='stretch'):
        st.session_state.chat_id = store.create()
        st.rerun()
    chats = store.list()
    ids = [c['id'] for c in chats]
    if not ids:
        st.session_state.chat_id = store.create()
        st.rerun()
    if st.session_state.get('chat_id') not in ids:
        st.session_state.chat_id = ids[0]
    labels = {c['id']:c['title'] for c in chats}
    selected = st.selectbox('Saved chats', ids, index=ids.index(st.session_state.chat_id),
                            format_func=lambda value: labels[value])
    if selected != st.session_state.chat_id:
        st.session_state.chat_id = selected
        st.rerun()
    cid = st.session_state.chat_id
    with st.form('rename_'+cid):
        title = st.text_input('Chat title', value=labels[cid], max_chars=100)
        if st.form_submit_button('Rename'):
            if title.strip():
                store.rename(cid,title)
                st.rerun()
            st.error('Enter a title.')
    with st.expander('Delete this chat'):
        confirm = st.checkbox('Permanently delete this conversation', key='confirm_'+cid)
        if st.button('Delete', disabled=not confirm):
            store.delete(cid)
            del st.session_state.chat_id
            st.rerun()
    st.divider()
    manifest_path = settings.data / 'manifest.json'
    manifest = read_json(manifest_path) if manifest_path.exists() else None
    st.caption('Dataset: '+(manifest['dataset_version'] if manifest else 'Not indexed'))
    st.caption('Only recent exchanges are used as active memory. Full transcripts remain saved.')
    show_retrieval=st.checkbox('Show retrieval details',value=False,
        help='Inspect search questions, active history, and passages for answer-quality review. Older answers may have no trace.')

has_key = bool(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))
if not manifest or not has_key:
    st.warning('Setup required: add your four PDFs, review page selections, configure a free-tier API key, and run ingestion. See README.md.')

with st.expander('Topics and data handling'):
    st.write('Ask about undergraduate academic rules, student procedures, CFD facilities, societies, hostels, scholarships, and study loans.')
    st.write('Relevant messages and document passages are sent to Google. Free-tier data may be used to improve its products. Avoid sharing personal records. Chats are saved locally without accounts.')
    st.write('Examples: “How do I withdraw from a course?” · “What conditions apply to continuing a merit scholarship?” · “What hostel facilities are described for CFD?”')

turns = store.turns(cid)
unfinished = False
for turn in turns:
    with st.chat_message('user'):
        st.write(turn['question'])
    with st.chat_message('assistant'):
        if turn['status']=='completed':
            st.markdown(turn['answer'], unsafe_allow_html=False)
            for citation in turn['citations']:
                with st.expander('['+citation['id']+'] Sources and passage'):
                    for ref in citation['references']:
                        st.write(f"{ref['title']} — {ref['section']}")
                        st.caption(f"PDF page {ref['pdf_page']} · Printed label {ref['printed_label']} · Campus: {ref['campus']} · Degree: {ref['degree']}")
                        if ref.get('url','').startswith(('https://','http://')):
                            st.link_button('Original source', ref['url'])
                        if ref.get('collection_date'):
                            st.caption('Snapshot collected '+ref['collection_date'])
                    st.text(citation['excerpt'])
            st.caption(f"{turn['model']} · Dataset {turn['dataset_version']} · {turn['latency']:.1f}s")
        else:
            unfinished = True
            st.warning(turn['error'] or 'This question was interrupted. Retry to finish it.')
            left,right = st.columns(2)
            if left.button('Retry', key='retry_'+turn['id'], disabled=not (manifest and has_key)):
                with st.spinner('Finding evidence and answering…'):
                    service.retry(turn['id'])
                st.rerun()
            if right.button('Discard question',key='discard_'+turn['id']):
                store.discard(turn['id'])
                st.rerun()
        if show_retrieval:
            trace=turn.get('diagnostics',{})
            with st.expander('Retrieval and history details'):
                if trace:
                    st.write('Route: '+trace.get('route','unknown'))
                    if trace.get('search_question'):
                        st.write('Search question: '+trace['search_question'])
                    if trace.get('history_context'):
                        st.text('Active conversation context:\n'+trace['history_context'])
                    for retrieved in trace.get('retrieved',[]):
                        packed = retrieved['chunk_id'] in trace.get('packed_source_ids',{}).values()
                        st.caption('Included in answer evidence' if packed else 'Retrieved but outside evidence budget')
                        st.write(retrieved['references'])
                        st.text(retrieved['passage'])
                else:
                    st.caption('This older answer was saved before retrieval tracing was added.')

question = st.chat_input('Ask about FAST undergraduate policies or CFD services',
    disabled=unfinished or not manifest or not has_key, max_chars=6000, submit_mode='disable')
if question:
    with st.spinner('Finding evidence and answering…'):
        service.ask(cid,question)
    st.rerun()
