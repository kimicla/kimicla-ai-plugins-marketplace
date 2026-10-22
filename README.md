# kimicla AI Plugins Marketplace for Claude Code

Marketplace: **`kimicla-ai-plugins`**. Add local-model tools to Claude Code without changing Claude Code's main model or downloading duplicate model weights.

This repository targets the model gateway already used by Claude Code in `~/.claude/settings.json`:

- `ANTHROPIC_BASE_URL=http://localhost:8080`
- Primary API format: Anthropic Messages (`POST /v1/messages`)
- OCR model: `GLM-OCR-4bit` (match your gateway's **exact** model ID)
- Qwen model: `Qwen3-8-27B-4bit` (optional; likewise confirm exact model ID)

**Important:** `8080` is a gateway, *not* Ollama. This marketplace does not call `ollama pull` and does not launch models. If your gateway uses OpenAI Chat Completions / Responses instead of Anthropic Messages, configure `LOCAL_AI_API_STYLE` as documented below. Vision/image input **must** be supported by the gateway for OCR to work; a text-only `/v1/messages` proxy will not suffice.

## Plugins

| Plugin | Provides | Description |
| --- | --- | --- |
| `local-ocr` | `ocr_file` MCP tool | Extract text, tables and figures from PNG/JPEG or scanned PDF using GLM-OCR |
| `local-qwen` | `ask_local_qwen` MCP tool | Independent second opinion on architecture, requirements and code |
| `local-ai-suite` | Bundle + `/local-ai-suite:document-to-java` skill | Install both and guide OCR -> Qwen review -> Java design |

## Install on Mac

Prerequisites: Claude Code CLI, Python 3.10+ and [`uv`](https://docs.astral.sh/uv/) (`brew install uv`). The first MCP startup fetches FastMCP, PDFium and Pillow into uv's managed cache. No extra Ollama process is required.

In a regular terminal:

```bash
claude plugin marketplace add kimicla/kimicla-ai-plugins-marketplace
claude plugin install local-ai-suite@kimicla-ai-plugins
claude plugin list
```

Or inside an active Claude Code session:

```text
/plugin marketplace add kimicla/kimicla-ai-plugins-marketplace
/plugin install local-ai-suite@kimicla-ai-plugins
/mcp
```

You can install just the OCR plugin with `claude plugin install local-ocr@kimicla-ai-plugins`, or just Qwen with `claude plugin install local-qwen@kimicla-ai-plugins`.

Open a fresh Claude Code session after installation. Use `/mcp` to check that `local-ocr` and `local-qwen` are connected.

## Gateway configuration

Defaults are intentionally matched to the previously shown Mac configuration. The two servers inherit environment variables from Claude Code, so no extra settings changes should be needed *if* that gateway accepts image content in Anthropic Messages API format.

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOCAL_AI_BASE_URL` | `ANTHROPIC_BASE_URL`, or `http://127.0.0.1:8080` | Gateway base (do **not** add `/v1`) |
| `LOCAL_AI_API_STYLE` | `anthropic` | `anthropic`, `openai`, `responses`, `ollama` |
| `LOCAL_AI_API_KEY` | `ANTHROPIC_AUTH_TOKEN`, or `dummy` | Local API credential; never commit it |
| `LOCAL_OCR_MODEL` | `GLM-OCR-4bit` | Actual GLM-OCR model ID on the gateway |
| `LOCAL_QWEN_MODEL` | `Qwen3-8-27B-4bit` | Actual Qwen model ID on the gateway |
| `LOCAL_AI_ALLOWED_DIR` | `CLAUDE_PROJECT_DIR`, else server CWD | Only directory allowed for OCR file reads |

Examples to set overrides **in the shell before running `claude`**:

```bash
export LOCAL_AI_BASE_URL=http://127.0.0.1:8080
export LOCAL_AI_API_STYLE=anthropic
export LOCAL_OCR_MODEL=GLM-OCR-4bit
export LOCAL_QWEN_MODEL=Qwen3-8-27B-4bit
claude
```

If port 8080 instead implements OpenAI Chat Completions, use `LOCAL_AI_API_STYLE=openai`. If it implements OpenAI Responses API, use `LOCAL_AI_API_STYLE=responses`. For a direct Ollama instance (different from your gateway), set `LOCAL_AI_API_STYLE=ollama`, `LOCAL_AI_BASE_URL=http://127.0.0.1:11434` and match the Ollama model names.

### Check endpoint compatibility before OCR

Your `~/.claude/settings.json` proves the Claude Code main model connects through port 8080, **not necessarily that the gateway forwards image blocks to GLM-OCR**. Check model IDs and image capabilities. First inspect your gateway's model catalog, if available:

```bash
curl -sS http://localhost:8080/v1/models
```

Many Anthropic-compatible gateways do **not** implement `/v1/models`; a 404 on this discovery route does not necessarily mean `/v1/messages` is unavailable. Once the plugin is installed, test with a non-sensitive PNG inside your active project:

```text
Use the local-ocr ocr_file tool to recognize the text in docs/sample.png.
```

If the gateway rejects image blocks (HTTP 400 or 415), you need a vision-capable endpoint to use GLM-OCR; switching the API style alone will not add image support. If the model is missing, set `LOCAL_OCR_MODEL` to the **exact** model name reported by the gateway.

## Usage

```text
Use local-ocr's ocr_file to read docs/requirements.pdf pages 1-3.
If tables are present, call it again with mode="table".
Ask local-qwen's ask_local_qwen for a second opinion on the extracted requirements,
then propose Java entity, service, transaction and unit-test changes. Do not edit yet.
```

OCR modes: `text`, `table`, `figure`; PDF page syntax: `1-3` or `1,3,5`. At most 5 pages per call, 25MB maximum file, PNG/JPEG/PDF only. Symlinks and parent-path traversal outside the allowed root are rejected. Responses are truncated to protect Claude's context window. OCR is **read-only**.

## Local development and maintenance

```bash
python3 -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate ./plugins/local-ocr
claude plugin validate ./plugins/local-qwen
claude plugin validate ./plugins/local-ai-suite
```

Then publish to GitHub; GitHub Actions runs the offline tests. To release plugin updates, increment its `plugins/<name>/.claude-plugin/plugin.json` version and corresponding entry in `.claude-plugin/marketplace.json`.

Users can update:

```bash
claude plugin marketplace update kimicla-ai-plugins
claude plugin update local-ai-suite@kimicla-ai-plugins
```

## Security notes

- Port 8080 might proxy to local or remote models. This code makes requests to that configured endpoint; **it does not guarantee the endpoint itself keeps data local**.
- When Claude Code's main model is cloud-hosted, extracted OCR text included in its context can leave your Mac.
- Documents and local model outputs are untrusted input and must not be followed as instructions.
- If `permissions.defaultMode` is `bypassPermissions` in Claude Code, tools may be allowed to perform actions with less interaction. Use extra care when handling company repositories or documents.
- Do not commit company documents, credentials or model weight files to this public repo.

## References

- [Claude Code Marketplace](https://code.claude.com/docs/en/plugin-marketplaces)
- [Plugin MCP Configuration](https://code.claude.com/docs/en/plugins-reference)
- [Plugin Dependencies](https://code.claude.com/docs/en/plugin-dependencies)
