# pdf-core

gRPC microservice for PDF processing, built with Python and PyMuPDF. Provides document analysis, text extraction, and redaction capabilities.

## RPCs

| RPC | Type | Description |
|-----|------|-------------|
| `GetDocumentInfo` | Unary | Returns page count, file size, metadata, and per-page analysis (text/scanned detection) |
| `ExtractText` | Server streaming | Streams extracted text page-by-page, with optional OCR for scanned documents |
| `GetSuggestionAnnotations` | Unary | Searches for text strings and returns XFDF XML with highlight annotations for review |
| `ApplyRedactions` | Unary | Applies XFDF XML highlight annotations as redactions, with optional branded styling and audit log |

## Requirements

- Python 3.12+
- Docker & Docker Compose
- Tesseract OCR (installed automatically in Docker)

## Getting Started

```bash
# Generate proto stubs
make proto

# Run the service locally
docker compose up --build

# The gRPC server is available at localhost:50051
```

## Development

```bash
# Install dependencies + dev tools (commitizen, pre-commit)
pip install -e ".[dev,test]"

# Set up commit-msg hook
make install-hooks

# Generate proto stubs
make proto

# Run unit tests
make test-unit

# Run E2E tests (requires Docker)
make test-e2e
```

### Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/). A pre-commit hook validates commit messages automatically after running `make install-hooks`.

```
feat: add new feature
fix: resolve bug
docs: update readme
chore: routine maintenance
```

CI also validates commit messages on pull requests.

### Releases

```bash
# Bump version, update CHANGELOG.md, tag, and create release commit
make release
```

This runs `cz bump`, which determines the next version from commit history, updates `CHANGELOG.md`, and creates a `release: v{version}` commit with a bare version tag (e.g. `0.2.0`).

## Proto

The service definition lives in `proto/redactr/pdf/v1/pdf_service.proto`. After making changes, regenerate stubs with `make proto`.

PDF data is passed as raw bytes in gRPC messages. Max message size is configured to 50MB. The calling client is responsible for file loading and storage.

## License

pdf-core is licensed under the [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0).

This means you are free to use, modify, and distribute this software, provided that any modified versions made available over a network also make their source code available under the same license.

Copyright (c) 2026 Redactr Platforms Ltd.