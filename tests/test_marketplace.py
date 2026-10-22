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
    def test_manifest(self):
        catalog=json.loads((ROOT/'.claude-plugin/marketplace.json').read_text())
        self.assertEqual([p['name'] for p in catalog['plugins']],['local-ocr'])
        plugin=json.loads((ROOT/'plugins/local-ocr/.claude-plugin/plugin.json').read_text())
        self.assertEqual(plugin['version'],catalog['plugins'][0]['version'])
        config=json.loads((ROOT/'plugins/local-ocr/.mcp.json').read_text())
        self.assertIn('local-ocr',config['mcpServers'])
        self.assertTrue((ROOT/'plugins/local-ocr/scripts/start.sh').stat().st_mode & 0o100)

    def test_default_without_settings(self):
        with tempfile.TemporaryDirectory() as td,patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td},clear=True):
            self.assertEqual(ocr.config(),('http://127.0.0.1:8080','anthropic','GLM-OCR-4bit','dummy'))

    def test_reads_claude_settings_without_process_env(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td,'settings.json').write_text(json.dumps({'env': {
                'ANTHROPIC_BASE_URL':'http://localhost:8080',
                'ANTHROPIC_AUTH_TOKEN':'internal-token',
                'ANTHROPIC_MODEL':'Ornith-1-5-35B-A3B-MLX-4bit',
                'LOCAL_OCR_MODEL':'GLM-OCR-4bit'}}))
            with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td},clear=True):
                self.assertEqual(ocr.config(),('http://localhost:8080','anthropic','GLM-OCR-4bit','internal-token'))

    def test_process_env_takes_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td,'settings.json').write_text(json.dumps({'env':{
                'ANTHROPIC_BASE_URL':'http://localhost:8080',
                'ANTHROPIC_AUTH_TOKEN':'settings-token',
                'LOCAL_OCR_MODEL':'wrong'}}))
            with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td,
                                        'LOCAL_OCR_MODEL':'GLM-OCR-4bit',
                                        'ANTHROPIC_AUTH_TOKEN':'shell-token'},clear=True):
                self.assertEqual(ocr.config(),('http://localhost:8080','anthropic','GLM-OCR-4bit','shell-token'))

    def test_invalid_settings_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td,'settings.json').write_text('{invalid')
            with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td},clear=True):
                self.assertEqual(ocr.config()[2],'GLM-OCR-4bit')

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
            Path(td,'settings.json').write_text(json.dumps({'env':{
                'ANTHROPIC_BASE_URL':'http://localhost:8080',
                'ANTHROPIC_AUTH_TOKEN':'secret',
                'LOCAL_OCR_MODEL':'GLM-OCR-4bit'}}))
            with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td},clear=True):
                def fake(url,payload,headers):
                    self.assertEqual(url,'http://localhost:8080/v1/messages')
                    self.assertEqual(headers['x-api-key'],'secret')
                    self.assertEqual(payload['model'],'GLM-OCR-4bit')
                    self.assertEqual(payload['messages'][0]['content'][1]['type'],'image')
                    return {'content':[{'type':'text','text':'识别成功'}]}
                with patch.object(ocr,'post_json',side_effect=fake):
                    self.assertEqual(ocr.ocr_image('Text Recognition:',b'img'),'识别成功')

    def test_other_formats(self):
        responses={'openai':{'choices':[{'message':{'content':'ok'}}]},
                   'responses':{'output':[{'content':[{'type':'output_text','text':'ok'}]}]},
                   'ollama':{'response':'ok'}}
        for style,response in responses.items():
            with self.subTest(style=style),tempfile.TemporaryDirectory() as td:
                with patch.dict(os.environ,{'CLAUDE_CONFIG_DIR':td,'LOCAL_AI_API_STYLE':style},clear=True):
                    with patch.object(ocr,'post_json',return_value=response):
                        self.assertEqual(ocr.ocr_image('Read',b'image'),'ok')

if __name__=='__main__':unittest.main()
