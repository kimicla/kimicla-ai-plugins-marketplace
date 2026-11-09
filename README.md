# Claude Code OCR MCP Marketplace

Single plugin: **`local-ocr@kimicla-ai-plugins`**, supporting an optional shared local-model inference server.

**No duplicate model download required.** The OCR plugin reads inherited environment variables or `~/.claude/settings.json` (`$CLAUDE_CONFIG_DIR/settings.json` if configured). Process env takes precedence. With `LOCAL_BASE_URL` configured, GLM-OCR uses that endpoint; otherwise it uses Claude Code's Anthropic model.

- Claude Code main model: `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL`, and `ANTHROPIC_AUTH_TOKEN`.
- Local OCR (optional): `LOCAL_BASE_URL`, `LOCAL_OCR_MODEL` (default `GLM-OCR-4bit`), and optionally `LOCAL_OCR_API_KEY`.
- Both routes use Anthropic `/v1/messages` by default.

Claude Code's main model settings remain untouched. The OCR plugin calls the local GLM-OCR model **only when `LOCAL_BASE_URL` is configured**.

## Copy an image to the local OCR model without sending it to Copilot

With Claude Code using Copilot Bridge at `:4141` and your local model server at
`:8080`, **do not paste images as normal Claude Code message attachments**.
The native attachment path can send image bytes to the primary model and fail
if the Bridge/model does not support image input.

Instead, copy a screenshot into the macOS clipboard (Control+Command+Shift+4),
or copy an image from Preview/Finder. Then type this text command in Claude Code:

```text
/local-ocr:ocr-clipboard 帮我解释图片里的错误信息
```

The installed Skill runs a local command **before the main model sees its
prompt**. It reads macOS clipboard image data, calls `LOCAL_BASE_URL` with
`LOCAL_OCR_MODEL`, and injects **only the recognized text** into the
conversation. Images are never attached by this Skill. The existing MCP
`ocr_file` remains available for project files.

Add to the existing `env` object in `~/.claude/settings.json`:

```json
"LOCAL_BASE_URL": "http://127.0.0.1:8080",
"LOCAL_OCR_MODEL": "GLM-OCR-4bit"
```

The clipboard command requires an explicitly configured **loopback**
`LOCAL_BASE_URL`; it will not fall back to the Copilot Bridge (`:4141`) or
send images to a remote endpoint. The OCR result still flows as text to the
main model via Claude Code, so use only company-approved content.

The script requires macOS Swift (available via Apple Command Line Tools) and
the existing `uv` launcher. A plugin update and Claude Code restart are
required. Run this terminal check after copying an image:

```bash
cd ~/.claude/plugins/marketplaces/kimicla-ai-plugins/plugins/local-ocr
bash scripts/start.sh clipboard
```

Successful execution prints OCR text only. Errors go to stderr. If you already
pasted the original image attachment into the Claude Code message, remove it
and use the text slash command instead. This is an **explicit** opt-in path:
an MCP plugin cannot globally intercept native image paste.

## Routing behavior (v0.4.0)

Claude Code and the OCR MCP are two separate API callers. The OCR result
always goes back to Claude Code as an MCP tool response; Claude Code then
sends that text to its primary model in the normal tool flow. No direct OCR ->
Copilot HTTP forwarding is needed.

| Configuration | OCR request goes to | Model | Credential |
| --- | --- | --- | --- |
| `LOCAL_BASE_URL` **unset** | Claude Code's `ANTHROPIC_BASE_URL` (e.g. :4141) | `ANTHROPIC_MODEL` (vision required) | `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` |
| `LOCAL_BASE_URL` **set** | `LOCAL_BASE_URL` (e.g. :8080) | `LOCAL_OCR_MODEL` (default GLM-OCR-4bit) | `LOCAL_OCR_API_KEY` (default dummy; **never** Copilot token) |

For your setup with Copilot Bridge on :4141 and oMLX on :8080, keep
your existing Claude Code settings and **add these two keys**
inside the existing `env` object:

```json
{
  "LOCAL_BASE_URL": "http://127.0.0.1:8080",
  "LOCAL_OCR_MODEL": "GLM-OCR-4bit"
}
```

Do not replace the whole `settings.json` file with this excerpt.
The OCR plugin uses Anthropic `/v1/messages` by default. If oMLX instead
requires OpenAI Chat Completions, add
`"LOCAL_OCR_API_STYLE": "openai"`. Only if the local server requires its own
token, add `LOCAL_OCR_API_KEY`; it will not receive Copilot credentials.

**Important:** Without `LOCAL_BASE_URL`, the MCP does **not** try
`GLM-OCR-4bit` via Copilot. It invokes the configured main model with an image,
which requires that main model/proxy support vision. If unavailable, OCR
returns a clear error rather than silently falling back to another model.
For this reason, set `LOCAL_BASE_URL` when you intend to use the local GLM-OCR model.

`LOCAL_BASE_URL` is intentionally **shared** by future local-model plugins
(e.g. local ASR, embeddings, or auxiliary LLMs). Each plugin retains its own
model selector such as `LOCAL_OCR_MODEL`.
The previous `LOCAL_OCR_BASE_URL` and `LOCAL_AI_BASE_URL` are deprecated
aliases supported for compatibility. Precedence is:
`LOCAL_BASE_URL` → `LOCAL_OCR_BASE_URL` → `LOCAL_AI_BASE_URL`.
Remove the older keys from your configuration once updated.

Update the installed plugin:

```bash
claude plugin marketplace update kimicla-ai-plugins
claude plugin update local-ocr@kimicla-ai-plugins
```

Restart Claude Code, then run `/mcp` and test with a non-sensitive
image in the current project. Verify :8080 logs show a GLM-OCR request, while
the resulting text appears as an MCP tool result for the model on :4141.

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

Keep your existing `~/.claude/settings.json`. To enable a **separate** local GLM-OCR model, add `LOCAL_BASE_URL` and `LOCAL_OCR_MODEL` under the existing `env` object, as shown in the Routing section above. If you omit `LOCAL_BASE_URL`, the tool calls your main Anthropic-compatible vision model instead. If the local model server uses another image API format, set `LOCAL_OCR_API_STYLE=openai`, `responses`, or `ollama` as needed.

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

The selected OCR backend must support image inputs in the chosen API format. A plain `curl http://localhost:8080` only checks server reachability, not vision capability.

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
