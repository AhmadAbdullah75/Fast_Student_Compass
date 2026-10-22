"""Reviewed page selection, reproducible chunks and resumable embedding cache."""
import hashlib
import json
import re
import sqlite3
from time import sleep
from pathlib import Path
from pypdf import PdfReader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from chromadb.config import Settings as ChromaSettings
from .models import GeminiEmbeddings

PIPELINE_VERSION = 2

def digest(value):
    return hashlib.sha256(value).hexdigest()

def tokens(text):
    # Conservative local estimate; no tokenizer model or vocab download.
    # Provider tokenization varies. Budgets are estimates, not exact Gemini counts.
    return (len(text.encode('utf-8')) + 2) // 3

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    # Windows may briefly deny replacement while an editor/reader or antivirus
    # holds the destination. Retain the complete checkpoint and retry briefly.
    for attempt in range(8):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt==7:raise
            sleep(min(.02*2**attempt,.25))

def catalog(settings):
    return read_json(settings.root / 'sources.json')

def extract_page(page):
    # Truly blank PDF pages can lack /Contents; pypdf's layout mode raises.
    if hasattr(page, 'keys') and '/Contents' not in page:
        return ''
    if not hasattr(page, 'cropbox'):
        return page.extract_text(extraction_mode='layout') or ''
    # These university PDFs retain adjacent spread content at negative/off-page
    # coordinates. Layout extraction includes it and corrupts page citations.
    box = page.cropbox
    visible = []
    def visit(text, cm, tm, font, size):
        x = tm[4]*cm[0] + tm[5]*cm[2] + cm[4]
        y = tm[4]*cm[1] + tm[5]*cm[3] + cm[5]
        if float(box.left)-1 <= x <= float(box.right)+1 and float(box.bottom)-1 <= y <= float(box.top)+1:
            visible.append(text)
    page.extract_text(visitor_text=visit)
    return ''.join(visible)

def pdf_path(settings, source):
    # A clone carries the reviewed PDFs; older local workspaces may still use
    # data/originals. Neither location may be escaped by a source filename.
    bases = [(settings.root / 'dataset').resolve(), (settings.data / 'originals').resolve()]
    paths = [(base / source['filename']).resolve() for base in bases]
    if any(path.parent != base or path.suffix.lower() != '.pdf'
           for base, path in zip(bases, paths)):
        raise ValueError('Source filename must be a PDF directly inside dataset/ or data/originals.')
    return next((path for path in paths if path.is_file()), paths[0])

def audit(settings):
    """Extract all pages locally, without API requests or indexing."""
    results = []
    for source in catalog(settings)['sources']:
        path = pdf_path(settings, source)
        if not path.exists():
            results.append({'id':source['id'], 'missing':str(path)})
            continue
        reader = PdfReader(path)
        labels = reader.page_labels
        pages = []
        for index, page in enumerate(reader.pages):
            text = extract_page(page)
            pages.append({'pdf_page':index+1, 'printed_label':labels[index],
                          'characters':len(text.strip()), 'text':text,
                          'needs_review':len(text.strip()) < 80})
        report = {'id':source['id'], 'sha256':digest(path.read_bytes()),
                  'page_count':len(pages), 'pages':pages,
                  'note':'PDF labels may be defaults; verify against visible printed pages. Inspect tables and columns visually.'}
        write_json(settings.root / 'reports' / f"{source['id']}-audit.json", report)
        results.append({k:v for k,v in report.items() if k != 'pages'})
    write_json(settings.root / 'reports' / 'audit-summary.json', results)
    return results

def chunks(settings):
    spec = catalog(settings)
    if len(spec['sources']) != 4 or len({s['id'] for s in spec['sources']}) != 4:
        raise ValueError('Configure the four approved sources with unique IDs.')
    splitter = RecursiveCharacterTextSplitter(chunk_size=settings.chunk_size,
        chunk_overlap=settings.overlap, length_function=tokens,
        separators=['\n\n', '\n', '. ', ' ', ''], add_start_index=True)
    unique = {}
    hashes = {}
    for source in spec['sources']:
        path = pdf_path(settings, source)
        if not path.exists():
            raise ValueError(f'Missing PDF: {source["filename"]}. Add the dataset and run audit.')
        sha = digest(path.read_bytes())
        hashes[source['id']] = sha
        if source.get('reviewed_sha256') != sha or not source.get('sections'):
            raise ValueError(f'{source["id"]}: audit the PDF, configure reviewed sections, and set reviewed_sha256 first.')
        reader = PdfReader(path)
        texts = [extract_page(p) for p in reader.pages]
        # Only explicitly reviewed repeated lines may be removed. Never guess.
        remove = set(source.get('remove_lines', []))
        if any(not isinstance(line, str) or not line.strip() for line in remove):
            raise ValueError('remove_lines must contain nonempty exact header/footer lines.')
        for section in source['sections']:
            start, end = section['pdf_start'], section['pdf_end']
            if not (1 <= start <= end <= len(texts)):
                raise ValueError(f'Invalid PDF page range for {source["id"]}.')
            if section['campus'] not in ('all','CFD') or section['degree'] not in ('all','undergraduate'):
                raise ValueError('Only all/CFD and all/undergraduate sections can enter this index.')
            if not section.get('title'):
                raise ValueError('Each reviewed section needs a title.')
            section_text, spans = '', []
            for number in range(start, end+1):
                raw = texts[number-1]
                raw = '\n'.join(line for line in raw.splitlines() if line.strip() not in remove)
                # Page-level text overrides support reviewed tables and mixed-scope pages.
                override = section.get('text_overrides', {}).get(str(number))
                if override is not None:
                    raw = override
                if not raw.strip():
                    raise ValueError(f'{source["id"]} PDF page {number} has no text; review extraction/OCR.')
                label = section.get('printed_labels', {}).get(str(number), reader.page_labels[number-1])
                reference = {key:source.get(key,'') for key in
                    ('id','filename','title','url','publication_date','collection_date','extraction_method')}
                reference.update(section=section['title'], pdf_page=number,
                    pdf_page_index=number-1, printed_label=label,
                    campus=section['campus'], degree=section['degree'])
                offset = len(section_text)
                section_text += raw.strip() + '\n\n'
                spans.append((offset, len(section_text)-2, reference))
            # Split whole sections rather than pages so a rule can continue across
            # a page break. Attribute only pages whose text overlaps the chunk.
            previous_begin, previous_end = -1, 0
            for part in splitter.split_text(section_text):
                # LangChain's add_start_index assumes character overlap; our
                # length function uses estimated tokens, so map offsets explicitly.
                search_from = max(previous_begin+1, previous_end-settings.overlap*3-10, 0)
                begin = section_text.find(part, search_from)
                if begin < 0:
                    raise ValueError('Could not map a chunk back to its source pages.')
                previous_begin, previous_end = begin, begin+len(part)
                references = [ref for lo,hi,ref in spans if lo < begin+len(part) and hi > begin]
                normalized = re.sub(r'\s+', ' ', part).strip()
                identity = digest((section['campus']+'|'+section['degree']+'|'+normalized).encode())
                if identity in unique:
                    refs = json.loads(unique[identity].metadata['references'])
                    for reference in references:
                        if reference not in refs:
                            refs.append(reference)
                    unique[identity].metadata['references'] = json.dumps(refs)
                else:
                    unique[identity] = Document(page_content=part, metadata={
                        'chunk_id':identity, 'campus':section['campus'],
                        'degree':section['degree'], 'references':json.dumps(references)})
    config = {'embedding_model':settings.embedding_model,'dimensions':settings.dimensions,
              'chunk_size':settings.chunk_size,'overlap':settings.overlap,
              'pipeline_version':PIPELINE_VERSION, 'catalog':spec, 'files':hashes}
    version = digest(json.dumps(config, sort_keys=True).encode())
    return list(unique.values()), version, config

class CachedEmbeddings:
    def __init__(self, settings, delegate):
        self.delegate = delegate
        settings.data.mkdir(parents=True, exist_ok=True)
        self.path = settings.data / 'embedding-cache.sqlite3'
        self.namespace = f'{settings.embedding_model}:{settings.dimensions}:qa-prefix-v1'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS embeddings(key TEXT PRIMARY KEY, vector TEXT NOT NULL)')

    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            key = digest((self.namespace+'|'+text).encode())
            with sqlite3.connect(self.path) as db:
                row = db.execute('SELECT vector FROM embeddings WHERE key=?', (key,)).fetchone()
            if row:
                vector = json.loads(row[0])
            else:
                vector = self.delegate.embed_documents([text])[0]
                with sqlite3.connect(self.path) as db:
                    db.execute('INSERT OR REPLACE INTO embeddings VALUES(?,?)', (key,json.dumps(vector)))
            vectors.append(vector)
        return vectors

    def embed_query(self, text):
        return self.delegate.embed_query(text)

def ingest(settings, embedding=None):
    docs, version, config = chunks(settings)
    manifest_path = settings.data / 'manifest.json'
    if manifest_path.exists():
        old = read_json(manifest_path)
        if old['fingerprint'] == version:
            store = Chroma(collection_name=old['collection'], persist_directory=str(settings.data / 'chroma'),
                           client_settings=ChromaSettings(anonymized_telemetry=False))
            if store._collection.count() == len(docs):
                return {'status':'unchanged', **old}
    if not docs:
        raise ValueError('Reviewed source selection produced no chunks.')
    name = 'compass_'+version[:32]
    cache = CachedEmbeddings(settings, embedding or GeminiEmbeddings(settings))
    store = Chroma(collection_name=name, embedding_function=cache,
                   persist_directory=str(settings.data / 'chroma'), collection_metadata={'hnsw:space':'cosine'},
                   client_settings=ChromaSettings(anonymized_telemetry=False))
    # Resumable: upsert only missing IDs. A failed API call never publishes a new manifest.
    existing = set(store.get()['ids'])
    pending = [d for d in docs if d.metadata['chunk_id'] not in existing]
    for document in pending:
        store.add_documents([document], ids=[document.metadata['chunk_id']])
    manifest = {'fingerprint':version, 'collection':name, 'chunks':len(docs),
                'dataset_version':config['catalog']['dataset_version'], 'config':config}
    write_json(manifest_path, manifest)
    return {'status':'indexed', **manifest}

def open_index(settings):
    path = settings.data / 'manifest.json'
    if not path.exists():
        raise ValueError('No reviewed index exists. Add the PDFs, audit them, and run ingestion first.')
    manifest = read_json(path)
    cfg = manifest['config']
    if cfg['embedding_model'] != settings.embedding_model or cfg['dimensions'] != settings.dimensions:
        raise ValueError('Embedding settings differ from the index. Run ingestion with the new settings.')
    if (cfg['catalog'] != catalog(settings) or cfg['chunk_size'] != settings.chunk_size
            or cfg['overlap'] != settings.overlap or cfg['pipeline_version'] != PIPELINE_VERSION):
        raise ValueError('Source selection or chunking changed. Audit and ingest before answering.')
    for source in cfg['catalog']['sources']:
        path = pdf_path(settings, source)
        if not path.exists() or digest(path.read_bytes()) != cfg['files'][source['id']]:
            raise ValueError('An original PDF changed or is missing. Audit and ingest before answering.')
    store = Chroma(collection_name=manifest['collection'], embedding_function=GeminiEmbeddings(settings),
                   persist_directory=str(settings.data / 'chroma'),
                   client_settings=ChromaSettings(anonymized_telemetry=False))
    if store._collection.count() != manifest['chunks']:
        raise ValueError('Index is incomplete. Run ingestion again.')
    return store, manifest
