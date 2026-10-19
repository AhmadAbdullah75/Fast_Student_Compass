"""SQLite owns durable conversations; frontend state is only a UI cursor."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

def now():
    return datetime.now(timezone.utc).isoformat()

class ChatStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS conversations(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS turns(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                question TEXT NOT NULL, answer TEXT, citations TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL, error TEXT, model TEXT, dataset_version TEXT,
                created TEXT NOT NULL, completed TEXT, latency REAL);
            CREATE INDEX IF NOT EXISTS turn_chat ON turns(conversation_id, created);
            ''')
            columns={row['name'] for row in db.execute('PRAGMA table_info(turns)')}
            if 'diagnostics' not in columns:
                db.execute("ALTER TABLE turns ADD COLUMN diagnostics TEXT NOT NULL DEFAULT '{}'")
            if 'client_request_id' not in columns:
                db.execute('ALTER TABLE turns ADD COLUMN client_request_id TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS turn_request ON turns(client_request_id)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, cid=None):
        cid = cid or uuid4().hex
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO conversations VALUES(?,?,?,?)', (cid, 'New chat', now(), now()))
        return cid

    def list(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM conversations ORDER BY updated DESC')]

    def rename(self, cid, title):
        title = title.strip()[:100]
        if not title:
            raise ValueError('A chat title cannot be empty.')
        with self.connect() as db:
            db.execute('UPDATE conversations SET title=?,updated=? WHERE id=?', (title, now(), cid))

    def delete(self, cid):
        with self.connect() as db:
            db.execute('DELETE FROM conversations WHERE id=?', (cid,))

    def turns(self, cid):
        with self.connect() as db:
            # Timestamp resolution can collide (or the system clock can move
            # backwards). Serialized insertion order defines the transcript;
            # random UUIDs must never reorder equal-time questions.
            rows = [dict(r) for r in db.execute('SELECT * FROM turns WHERE conversation_id=? ORDER BY rowid', (cid,))]
        for row in rows:
            row['citations'] = json.loads(row['citations'])
            row['diagnostics'] = json.loads(row['diagnostics'])
        return rows

    def begin(self, cid, question, request_id=None):
        question = question.strip()
        if not question or len(question) > 6000:
            raise ValueError('Enter a question between 1 and 6,000 characters.')
        tid = uuid4().hex
        with self.connect() as db:
            # Serialize idempotency lookup + insert, even across HTTP requests.
            db.execute('BEGIN IMMEDIATE')
            if request_id:
                existing=db.execute('SELECT id,conversation_id,question FROM turns WHERE client_request_id=?',(request_id,)).fetchone()
                if existing:
                    if existing['conversation_id']!=cid or existing['question']!=question:
                        raise ValueError('This request ID was already used for a different question.')
                    return existing['id']
            if db.execute("SELECT 1 FROM turns WHERE conversation_id=? AND status IN ('pending','failed')", (cid,)).fetchone():
                raise ValueError('Retry or discard the unfinished question first.')
            db.execute('INSERT INTO turns(id,conversation_id,question,status,created,client_request_id) VALUES(?,?,?,?,?,?)',
                       (tid, cid, question, 'pending', now(),request_id))
            count = db.execute('SELECT COUNT(*) FROM turns WHERE conversation_id=?', (cid,)).fetchone()[0]
            if count == 1:
                db.execute('UPDATE conversations SET title=? WHERE id=?', (question[:65], cid))
            db.execute('UPDATE conversations SET updated=? WHERE id=?', (now(), cid))
        return tid

    def get_turn(self, tid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM turns WHERE id=?', (tid,)).fetchone()
        if row is None:
            raise ValueError('Question no longer exists.')
        return dict(row)

    def retry(self, tid):
        with self.connect() as db:
            db.execute("UPDATE turns SET status='pending',error=NULL WHERE id=? AND status IN ('pending','failed')", (tid,))

    def finish(self, tid, answer, citations, model, dataset, latency, diagnostics=None):
        with self.connect() as db:
            db.execute("UPDATE turns SET answer=?,citations=?,model=?,dataset_version=?,latency=?,status='completed',completed=?,error=NULL,diagnostics=? WHERE id=?",
                       (answer, json.dumps(citations), model, dataset, latency, now(), json.dumps(diagnostics or {}),tid))
            db.execute('UPDATE conversations SET updated=? WHERE id=(SELECT conversation_id FROM turns WHERE id=?)', (now(), tid))

    def fail(self, tid, message, diagnostics=None):
        with self.connect() as db:
            db.execute("UPDATE turns SET status='failed',error=?,diagnostics=? WHERE id=?", (message,json.dumps(diagnostics or {}),tid))

    def discard(self, tid):
        with self.connect() as db:
            db.execute("DELETE FROM turns WHERE id=? AND status!='completed'", (tid,))
