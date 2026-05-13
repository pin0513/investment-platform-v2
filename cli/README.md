# ipv2 CLI

Command-line interface for [investment-platform-v2](https://investment-platform-v2-yt3vv5n7za-de.a.run.app).

## Install

```bash
pip install -e ./cli
```

Or from the repo root (using the project's venv):

```bash
.venv/bin/pip install -e ./cli
.venv/bin/ipv2 --version
```

## Quick Start

```bash
# 1. Authenticate
ipv2 auth login
# Prompts for email + password (getpass)

# 2. Check connectivity and token
ipv2 doctor

# 3. Preview an import file (no API mutations)
ipv2 import preview cli/examples/import-example.yaml

# 4. Apply the import
ipv2 import apply cli/examples/import-example.yaml

# 5. View portfolio
ipv2 portfolio summary
ipv2 portfolio summary --ccy USD --format json
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IPV2_BASE_URL` | `https://investment-platform-v2-yt3vv5n7za-de.a.run.app` | API base URL |
| `IPV2_TOKEN` | - | Override bearer token (skips credentials file) |
| `IPV2_CONFIG_DIR` | `~/.ipv2` | Credentials + config directory |

### Config Files (layered)

Priority order (highest first):

1. CLI flag (`--base-url`)
2. Environment variable (`IPV2_BASE_URL`)
3. Project config `./.ipv2.yaml`
4. User config `~/.ipv2/config.yaml`
5. Built-in default

Example `~/.ipv2/config.yaml`:

```yaml
base_url: https://investment-platform-v2-yt3vv5n7za-de.a.run.app
```

### Credentials

Stored at `~/.ipv2/credentials` (JSON, 0600 permissions). Never commit this file.

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_at": "2026-05-14T00:00:00+00:00",
  "email": "you@example.com"
}
```

## Import File Format

See `examples/import-example.yaml` for a fully commented example.

```yaml
version: 1
default_owner: self   # used when account.owner is not set

accounts:
  - id: broker1       # local reference (not stored in DB)
    name: Fubon Securities
    type: BROKER_STOCK
    currency: TWD

holdings:
  - account: broker1
    symbol: 2330.TW
    quantity: "100"
    avg_cost: "550.00"
    opened_at: "2024-01-15"
```

### Ambiguity Protocol

The **iron law**: any ambiguity stops execution.

- **TTY (interactive):** Prompts you to resolve each ambiguity one-by-one.
- **Non-TTY (CI/scripts):** Prints all ambiguities to stderr and exits with code **4**.
- `--yes` skips the final confirmation prompt but does **NOT** auto-resolve ambiguities.
- `--on-conflict {skip,update,new-with-suffix,abort}` auto-resolves `IDENTITY_COLLISION`.

**Ambiguity types:**

| Kind | Trigger | Resolution options |
|------|---------|-------------------|
| `MISSING_OWNER` | Account has no `owner` and `default_owner` not set | set-self, abort |
| `IDENTITY_COLLISION` | Account name matches DB but fields differ | skip, update, new-with-suffix, abort |
| `MATH_MISMATCH` | `abs(qty * price - amount) / amount > 0.5%` | use-implied, use-stated, abort |
| `EXISTING_OPENING` | External ref `opening:account:symbol` already in DB | skip, abort |
| `MISSING_MARKET` | Symbol exists in multiple markets (P1.1 - extensible) | abort |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (auth, API error, config error) |
| 4 | **Ambiguity detected in non-interactive mode** |

## Commands

```
ipv2 --help
ipv2 auth login     [--email EMAIL]
ipv2 auth status
ipv2 auth refresh
ipv2 auth logout
ipv2 import preview <file> [--owner-default NAME] [--on-conflict CHOICE] [--format table|json]
ipv2 import apply   <file> [--owner-default NAME] [--on-conflict CHOICE] [--yes] [--dry-run]
ipv2 portfolio summary     [--ccy CCY] [--format table|json|yaml]
ipv2 doctor
```

## Development

```bash
cd cli
pytest tests/ -v
ruff check ipv2/ tests/
ruff format --check ipv2/ tests/
```
