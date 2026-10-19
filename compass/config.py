from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    chat_model: str = os.getenv('CHAT_MODEL', 'gemini-3.5-flash-lite')
    embedding_model: str = os.getenv('EMBEDDING_MODEL', 'gemini-embedding-2')
    dimensions: int = int(os.getenv('EMBEDDING_DIMENSIONS', '768'))
    chunk_size: int = 600
    overlap: int = 80
    k: int = 6
    fetch_k: int = 12
    evidence_budget: int = 4000
    history_budget: int = 2500

    @property
    def data(self):
        return self.root / 'data'

    def require_key(self):
        key = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not key:
            raise ValueError('Add your free-tier Google API key to .env before using the API.')
        return key
