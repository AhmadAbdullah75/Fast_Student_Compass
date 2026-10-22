"""Run from the project directory: python -m compass.cli --help."""
import argparse
import json
from .config import Settings
from .ingestion import audit, ingest, write_json, chunks, tokens
from .models import GeminiEmbeddings, chat_model
from .rag import friendly_error

def preflight(settings):
    settings.require_key()
    emb = GeminiEmbeddings(settings)
    doc = emb.embed_documents(['An undergraduate may ask the university office for clarification.'])[0]
    query = emb.embed_query('Who clarifies university policy?')
    response = chat_model(settings).invoke('Reply with the word READY only.')
    return {'chat_model':settings.chat_model, 'response':str(response.content),
            'embedding_model':settings.embedding_model, 'document_dimensions':len(doc),
            'query_dimensions':len(query),
            'note':'Access check only. This does not establish free billing status or remaining quota; verify AI Studio.'}

def main():
    parser = argparse.ArgumentParser(description='Local CFD Student Compass tools')
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('audit','prepare','preflight','ingest'):
        sub.add_parser(name)
    args = parser.parse_args()
    settings = Settings()
    try:
        if args.command=='audit':
            result = audit(settings)
        elif args.command=='prepare':
            docs, fingerprint, config = chunks(settings)
            write_json(settings.root/'reports/prepared-chunks.json',{'fingerprint':fingerprint,
                'chunks':[{'text':d.page_content,'metadata':d.metadata} for d in docs]})
            result = {'chunks':len(docs),'max_estimated_tokens':max(tokens(d.page_content) for d in docs),
                      'fingerprint':fingerprint,'api_calls':0}
        elif args.command=='preflight':
            result = preflight(settings)
        elif args.command=='ingest':
            result = ingest(settings)
            result = {key:result[key] for key in ('status','dataset_version','chunks','collection')}
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except Exception as exc:
        message = str(exc) if isinstance(exc,(ValueError,FileNotFoundError)) else friendly_error(exc)
        parser.exit(1, message+'\n')

if __name__=='__main__':
    main()
