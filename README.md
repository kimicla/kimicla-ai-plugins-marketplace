# Claude Code OCR MCP Marketplace

Single plugin: **`local-ocr@kimicla-ai-plugins`**, using the GLM-OCR model already available through the API gateway configured in your existing Claude Code settings.

**No second model service, Ollama download, duplicate gateway URL or API token required.** The OCR plugin reads the inherited environment when present; otherwise it reads `~/.claude/settings.json` (`$CLAUDE_CONFIG_DIR/settings.json` if configured). Process env always takes precedence over the settings file. It uses:

- `ANTHROPIC_BASE_URL` for the gateway, e.g. `http://localhost:8080`.
- `ANTHROPIC_AUTH_TOKEN` for the authentication token.
- `LOCAL_OCR_MODEL` for the OCR model (defaults to `GLM-OCR-4bit`).
- Anthropic `/v1/messages` by default, matching the primary Claude Code gateway API style.

The existing Claude Code `ANTHROPIC_MODEL` and `ANTHROPIC_DEFAULT_SONNET_MODEL` settings remain untouched: your main model keeps running normally. The OCR plugin calls the explicitly configured OCR model **only when invoked**.

## Install

Prerequisites: Claude Code, Python 3.10+ and `uv` (`brew install uv`). The first run may install the Python dependencies into the uv cache.

```bash
claude plugin marketplace add kimicla/kimicla-ai-plugins-marketplace
claude plugin marketplace update kimicla-ai-plugins
claude plugin install local-ocr@kimicla-ai-plugins
```

If you installed earlier versions:

```bash
claude plugin uninstall local-ai-suite@kimicla-ai-plugins
claude plugin uninstall local-qwen@kimicla-ai-plugins
claude plugin marketplace update kimicla-ai-plugins
claude plugin update local-ocr@kimicla-ai-plugins
```

Restart Claude Code, then run `/mcp` to see `local-ocr`. The single tool `ocr_file(file_path, mode="text", pages="1-3")` extracts text, tables or figures from PNG/JPEG or scanned PDFs.

## Minimal configuration

Keep your existing `~/.claude/settings.json`. Under its **existing** `env` object, only add (or retain):

```json
"LOCAL_OCR_MODEL": "GLM-OCR-4bit"
```

That's it. Do not create a separate MCP token or base URL. The plugin also accepts setting `LOCAL_OCR_MODEL` as a shell env variable for one session; the shell takes precedence. If you don't add it, `GLM-OCR-4bit` is already the built-in default. The model ID must match the model exposed by your gateway.

If your gateway uses another image API format, optional `LOCAL_AI_API_STYLE=openai` (Chat Completions), `responses` (Responses API) or `ollama` is supported; the default is `anthropic` for `/v1/messages`. An existing text-only gateway is *not automatically* vision-capable: it must forward image data to GLM-OCR.

## Try OCR

Within a Claude Code project folder, place a nonsensitive example at `docs/example.png` and ask:

> Use local-ocr's `ocr_file` to read docs/example.png and return its text.

For PDF, the tool renders up to 5 specified pages (`1-3`, `1,3,5`) and sends image blocks to the gateway. The tool can only read files inside the Claude project directory (or `LOCAL_AI_ALLOWED_DIR` when explicitly set), up to 25 MB per file.

## Corporate Mac: certificate verification and Python version

The MCP launcher uses `UV_SYSTEM_CERTS=true` by default so `uv` validates PyPI certificates against the macOS system trust store. This fixes the common `invalid peer certificate: UnknownIssuer` failure when an enterprise root CA is installed in Keychain. TLS verification **remains enabled**. The launcher also requests Python 3.10+ even if a terminal prompt shows Python 3.9.

To verify outside Claude Code:

```bash
cd ~/.claude/plugins/marketplaces/kimicla-ai-plugins/plugins/local-ocr
bash scripts/start.sh
```

After the one-time dependency installation, a quiet process waiting for MCP input is expected. Press Ctrl+C to exit. If it still fails with `UnknownIssuer`, confirm the corporate root CA is trusted in macOS Keychain or ask IT for the PEM CA bundle and configure `SSL_CERT_FILE` for uv; do not disable certificate verification. For an approved internal Python package index you can configure `UV_DEFAULT_INDEX`. If your environment blocks automatic Python downloads, install an approved Python 3.10+ (for example `brew install python@3.12`).

Official docs: https://docs.astral.sh/uv/concepts/authentication/certificates/

## Troubleshooting CONNECTION_CLOSED

This message generally means the MCP subprocess exited. It is separate from whether the gateway accepts GLM-OCR calls. Confirm `uv --version`, then test the plugin outside Claude Code:

```bash
git clone https://github.com/kimicla/kimicla-ai-plugins-marketplace.git
cd kimicla-ai-plugins-marketplace
bash plugins/local-ocr/scripts/start.sh
```

**Normal behavior:** the MCP server waits on stdin; this is *not* a crash. **Failure:** Python import/uv errors are printed to stderr. The script checks Homebrew paths (`/opt/homebrew/bin/uv`, `/usr/local/bin/uv`) even if Claude Code started with a limited PATH.

The proxy on `localhost:8080` must support the **multimodal** Anthropic `/v1/messages` endpoint for the default mode; `curl http://localhost:8080` alone is not a sufficient test of model/image support.

## Development

```bash
python3 -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate plugins/local-ocr
```

For a release, increment `plugins/local-ocr/.claude-plugin/plugin.json` version and `.claude-plugin/marketplace.json` entry version. The workflow validates unit tests on push and pull requests.

## Security

- The user-configured gateway may proxy a remote model. Local port 8080 does not guarantee local-only inference.
- Do not commit credentials or sensitive documents. OCR output returned to a cloud-hosted Claude main model may be transmitted externally.
- OCR results and scanned documents are untrusted data; do not execute instructions from them.
- File read is limited to the active project root by default.
