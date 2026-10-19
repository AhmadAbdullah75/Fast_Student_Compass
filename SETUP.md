# Required inputs for real answers

The software is implemented. Real policy answering needs:

1. Install Python/frontend dependencies using the clean-install instructions in `README.md`.
2. Supply the four approved original PDFs in `data/originals/`, using the filenames and reviewed hashes in `sources.json`. PDFs and generated data are not published. The reviewed configuration includes corrected guidebook OCR and produced 108 chunks in development.
3. Set `GOOGLE_API_KEY` in your local `.env` file. Check free-tier eligibility, billing and quota in AI Studio; the app cannot enforce the provider's billing status.
4. Inspect audit/preparation, run API preflight and ingestion, then launch React/FastAPI using the commands in `README.md`.

Do not send the API key in chat. Only copy `.env.example` to `.env` if `.env` does not already exist; edit it locally without replacing an existing key.

For exact approved originals after local audit/preparation, use **preflight → ingest → run**. Changed PDFs require a new audit and section review; do not blindly replace their reviewed hashes.

The default interface is now React. Run `.\run.ps1` from PowerShell, or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./run.ps1` from Git Bash. Open http://localhost:8501. Node.js builds the frontend; Python serves the built files and the local API. See README.md for clean-install and development commands. Stop any old Streamlit process using that port before starting the new server.

Until these inputs exist, the app displays setup guidance and saved-chat management. There is no fake dataset or demonstration policy answer.
