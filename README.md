# Investment Platform v2

Multi-asset portfolio platform — TW stocks, US stocks, crypto, bank deposits, funds — with Claude Code MCP integration and AI-generated weekly reports.

## Development

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Deployment

See `docs/api.md` and `cloudbuild.yaml`. Production: https://invest.paulfun.net
