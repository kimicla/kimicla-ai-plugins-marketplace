"""Offline tests for Claude Code local-ocr marketplace."""
from __future__ import annotations
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
mod=types.ModuleType('fastmcp')
class FakeFastMCP:
    def __init__(self,name):self.name=name
    def tool(self,fn):return fn
mod.FastMCP=FakeFastMCP
sys.modules['fastmcp']=mod
spec=importlib.util.spec_from_file_location('local_ocr',ROOT/'plugins/local-ocr/server.py')
ocr=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocr)

class OCRTests(unittest.TestCase):
    def test_clipboard_skill_and_launcher(self):
        skill = (ROOT/'plugins/local-ocr/skills/ocr-clipboard/SKILL.md').read_text()
        self.assertIn('disable-model-invocation: true', skill)
        self.assertIn('start.sh" clipboard', skill)
        self.assertIn('!'+chr(96)+'bash ', skill)
        self.assertTrue((ROOT/'plugins/local-ocr/scripts/clipboard.swift').is_file())
        launcher = (ROOT/'plugins/local-ocr/scripts/start.sh').read_text()
        self.assertIn('== "clipboard"', launcher)

    def test_loopback_ocr_disables_proxies_and_redirects(self):
        from unittest.mock import MagicMock
        opener = MagicMock()
        response = MagicMock()
        response.__enter__.return_value = response
        opener.open.return_value = response
        with patch.object(ocr.urllib.request, "build_opener",
                          return_value=opener) as build, patch.object(
                              ocr.json, "load", return_value={"ok": True}
                          ):
            self.assertEqual(
                ocr.post_json("http://127.0.0.1:8080/v1/messages", {}, {}),
                {"ok": True}
            )
        self.assertIsInstance(build.call_args.args[0], ocr.urllib.request.ProxyHandler)
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], ocr.NoRedirect)

    def test_clipboard_never_falls_back_to_main_model(self):
        path = ROOT/'plugins/local-ocr/clipboard.py'
        spec = importlib.util.spec_from_file_location("clipboard", path)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"server": ocr}):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": td,
            "ANTHROPIC_BASE_URL": "http://localhost:4141",
            "ANTHROPIC_MODEL": "gpt-4.1",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "LOCAL_BASE_URL"):
                module.validate_local_route()
            with patch.object(module, "read_clipboard") as reader:
                with self.assertRaises(RuntimeError):
                    module.transcribe()
                reader.assert_not_called()
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": td,
            "LOCAL_BASE_URL": "https://example.com",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "loopback"):
                module.validate_local_route()
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": td,
            "LOCAL_BASE_URL": "http://127.0.0.1:8080",
            "LOCAL_OCR_MODEL": "GLM-OCR-4bit",
        }, clear=True):
            self.assertEqual(module.validate_local_route(), "http://127.0.0.1:8080")
            with patch.object(module, "read_clipboard", return_value=b"image"), \
                 patch.object(ocr, "ocr_image", return_value="recognized") as called:
                self.assertEqual(module.transcribe(), "recognized")
                self.assertEqual(called.call_args.args[1], b"image")

    def test_launcher_uses_platform_certificates_and_supported_python(self):
        script=(ROOT/'plugins/local-ocr/scripts/start.sh').read_text()
        self.assertIn('UV_SYSTEM_CERTS="${UV_SYSTEM_CERTS:-true}"',script)
        self.assertIn("--python '>=3.10'",script)
        self.assertNotIn('--allow-insecure-host',script)

    def test_manifest(self):
        catalog=json.loads((ROOT/'.claude-plugin/marketplace.json').read_text())
        self.assertEqual([p['name'] for p in catalog['plugins']],['local-ocr'])
        plugin=json.loads((ROOT/'plugins/local-ocr/.claude-plugin/plugin.json').read_text())
        self.assertEqual(plugin['version'],catalog['plugins'][0]['version'])
        config=json.loads((ROOT/'plugins/local-ocr/.mcp.json').read_text())
        self.assertIn('local-ocr',config['mcpServers'])
        self.assertTrue((ROOT/'plugins/local-ocr/scripts/start.sh').stat().st_mode & 0o100)

    def test_missing_main_model_gives_actionable_error(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(
            os.environ, {"CLAUDE_CONFIG_DIR": td}, clear=True
        ):
            with self.assertRaisesRegex(ValueError, "ANTHROPIC_MODEL"):
                ocr.config()

    def test_no_local_url_uses_claude_model_and_token(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "settings.json").write_text(json.dumps({"env": {
                "ANTHROPIC_BASE_URL": "http://localhost:4141",
                "ANTHROPIC_AUTH_TOKEN": "copilot-token",
                "ANTHROPIC_MODEL": "gpt-4.1",
                "LOCAL_OCR_MODEL": "GLM-OCR-4bit"
            }}))
            with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": td}, clear=True):
                self.assertEqual(
                    ocr.config(),
                    ("http://localhost:4141", "anthropic", "gpt-4.1", "copilot-token")
                )

    def test_local_url_routes_to_ocr_and_never_copies_copilot_key(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "settings.json").write_text(json.dumps({"env": {
                "ANTHROPIC_BASE_URL": "http://localhost:4141",
                "ANTHROPIC_AUTH_TOKEN": "copilot-secret",
                "ANTHROPIC_MODEL": "gpt-4.1",
                "LOCAL_BASE_URL": "http://localhost:8080",
                "LOCAL_OCR_MODEL": "GLM-OCR-4bit"
            }}))
            with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": td}, clear=True):
                self.assertEqual(
                    ocr.config(),
                    ("http://localhost:8080", "anthropic", "GLM-OCR-4bit", "dummy")
                )
                with patch.object(ocr, "post_json", return_value={
                    "content": [{"type": "text", "text": "identified text"}]
                }) as request:
                    self.assertEqual(
                        ocr.ocr_image("Text Recognition:", b"img"), "identified text"
                    )
                    self.assertEqual(
                        request.call_args.args[0], "http://localhost:8080/v1/messages"
                    )
                    self.assertEqual(request.call_args.args[1]["model"], "GLM-OCR-4bit")
                    self.assertNotIn(
                        "copilot-secret", str(request.call_args.args[2])
                    )

    def test_old_local_base_url_is_still_supported(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": td,
            "LOCAL_OCR_BASE_URL": "http://localhost:8081",
            "LOCAL_OCR_MODEL": "GLM-OCR-4bit",
        }, clear=True):
            self.assertEqual(
                ocr.config(),
                ("http://localhost:8081", "anthropic", "GLM-OCR-4bit", "dummy")
            )

    def test_generic_local_base_url_precedes_old_alias(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": td,
            "ANTHROPIC_BASE_URL": "http://localhost:4141",
            "ANTHROPIC_MODEL": "gpt-4.1",
            "LOCAL_BASE_URL": "http://localhost:8080",
            "LOCAL_OCR_BASE_URL": "http://localhost:8081",
            "LOCAL_AI_BASE_URL": "http://localhost:8082",
        }, clear=True):
            self.assertEqual(
                ocr.config(),
                ("http://localhost:8080", "anthropic", "GLM-OCR-4bit", "dummy")
            )

    def test_local_api_key_and_style_override(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": td,
            "ANTHROPIC_BASE_URL": "http://localhost:4141",
            "ANTHROPIC_MODEL": "gpt-4.1",
            "ANTHROPIC_AUTH_TOKEN": "copilot-secret",
            "LOCAL_BASE_URL": "http://localhost:8080",
            "LOCAL_OCR_API_KEY": "local-secret",
            "LOCAL_OCR_API_STYLE": "openai",
        }, clear=True):
            self.assertEqual(ocr.config(), (
                "http://localhost:8080", "openai", "GLM-OCR-4bit", "local-secret"
            ))

    def test_read_scope(self):
        with tempfile.TemporaryDirectory() as allowed,tempfile.TemporaryDirectory() as outside:
            root=Path(allowed)
            (root/'sample.png').write_bytes(b'png')
            (root/'link.pdf').symlink_to(Path(outside)/'not-here.pdf')
            with patch.dict(os.environ,{'LOCAL_AI_ALLOWED_DIR':allowed}):
                self.assertEqual(ocr.validate_file('sample.png'),root/'sample.png')
                with self.assertRaises(ValueError): ocr.validate_file('../abc.png')
                with self.assertRaises(ValueError): ocr.validate_file('link.pdf')
                with patch.object(ocr,'ocr_image',return_value='text'):
                    self.assertIn('text',ocr.ocr_file('sample.png'))

    def test_pdf_page_ranges(self):
        self.assertEqual(ocr.parse_pages('1-3,5',10),[1,2,3,5])
        for bad in ('1-99','../3','0'):
            with self.assertRaises(ValueError):ocr.parse_pages(bad,100)
        with self.assertRaises(ValueError):ocr.parse_pages('8',3)

    def test_anthropic_payload_and_auth(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "settings.json").write_text(json.dumps({"env": {
                "ANTHROPIC_BASE_URL": "http://localhost:4141",
                "ANTHROPIC_AUTH_TOKEN": "copilot-secret",
                "ANTHROPIC_MODEL": "gpt-4.1"
            }}))
            with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": td}, clear=True):
                def fake(url, payload, headers):
                    self.assertEqual(url, "http://localhost:4141/v1/messages")
                    self.assertEqual(headers["x-api-key"], "copilot-secret")
                    self.assertEqual(payload["model"], "gpt-4.1")
                    self.assertEqual(payload["messages"][0]["content"][1]["type"], "image")
                    return {"content": [{"type": "text", "text": "识别成功"}]}
                with patch.object(ocr, "post_json", side_effect=fake):
                    self.assertEqual(
                        ocr.ocr_image("Text Recognition:", b"img"), "识别成功"
                    )

    def test_other_formats(self):
        responses={'openai':{'choices':[{'message':{'content':'ok'}}]},
                   'responses':{'output':[{'content':[{'type':'output_text','text':'ok'}]}]},
                   'ollama':{'response':'ok'}}
        for style,response in responses.items():
            with self.subTest(style=style),tempfile.TemporaryDirectory() as td:
                with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td,'LOCAL_BASE_URL':'http://127.0.0.1:8080','LOCAL_OCR_API_STYLE':style},clear=True):
                    with patch.object(ocr,'post_json',return_value=response):
                        self.assertEqual(ocr.ocr_image('Read',b'image'),'ok')

if __name__=='__main__':unittest.main()
