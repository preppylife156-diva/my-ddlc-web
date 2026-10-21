import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import HTTPServer
from io import BytesIO
from pathlib import Path

import bridge


class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), bridge.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:%s' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def setUp(self):
        with bridge.lock:
            bridge.runtime_labels.clear()
            bridge.results.clear()
            bridge.queue.clear()
            bridge.last_game_seen = 0.0
            bridge.next_id = 1

    def request(self, path, data=None, method=None, content_type=None, origin=None, token='default'):
        url = self.base + path
        if token is not None:
            url += ('&' if '?' in path else '?') + 'token=' + (bridge.TOKEN if token == 'default' else token)
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        if origin:
            headers['Origin'] = origin
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        return urllib.request.urlopen(request)

    def post_json(self, path, payload):
        return self.request(path, json.dumps(payload).encode('utf-8'), 'POST', 'application/json')

    def make_zip(self, entries):
        archive = BytesIO()
        with zipfile.ZipFile(archive, 'w') as output:
            for name, content in entries:
                output.writestr(name, content)
        return archive.getvalue()

    def test_authentication_token_and_origin(self):
        page = self.request('/').read().decode('utf-8')
        self.assertIn(bridge.TOKEN, page)
        with self.assertRaises(urllib.error.HTTPError) as missing_token:
            self.request('/recommended', token=None)
        self.assertEqual(missing_token.exception.code, 403)
        missing_token.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as bad_token:
            self.request('/recommended', token='not-the-token')
        self.assertEqual(bad_token.exception.code, 403)
        bad_token.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as bad_origin:
            self.request('/recommended', origin='https://untrusted.example')
        self.assertEqual(bad_origin.exception.code, 403)
        bad_origin.exception.close()
        self.assertFalse(bridge.allowed_origin('null'))
        self.assertTrue(bridge.allowed_origin('http://127.0.0.1:8765'))

    def test_browser_package_upload_serve_remove_and_invalid_zip(self):
        raw = self.make_zip([('index.html', '<h1>Browser package</h1>'), ('assets/app.js', 'ok')])
        package = json.loads(self.request('/package', raw, 'POST', 'application/zip').read())
        self.assertEqual(package['files'], ['index.html', 'assets/app.js'])
        served = self.request('/package/%s/index.html' % package['package_id'], origin='null')
        self.assertEqual(served.read(), b'<h1>Browser package</h1>')
        self.request('/package/%s' % package['package_id'], method='DELETE')
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request('/package/%s/index.html' % package['package_id'])
        self.assertEqual(missing.exception.code, 404)
        missing.exception.close()
        with self.assertRaises(urllib.error.HTTPError) as invalid:
            self.request('/package', b'not a zip archive', 'POST', 'application/zip')
        self.assertEqual(invalid.exception.code, 400)
        invalid.exception.close()

    def test_zip_path_traversal_is_rejected(self):
        raw = self.make_zip([('../outside.txt', 'unsafe')])
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.request('/package', raw, 'POST', 'application/zip')
        self.assertEqual(rejected.exception.code, 400)
        rejected.exception.close()

    def test_scene_commands_require_live_game_labels(self):
        self.request('/poll')
        self.post_json('/result', {'message': 'labels ready', 'ok': True, 'labels': ['ch0_main', 'safe_scene']})
        rejected = None
        try:
            self.post_json('/command', {'command': 'scene missing_label'})
        except urllib.error.HTTPError as error:
            rejected = error
        self.assertIsNotNone(rejected)
        self.assertEqual(rejected.code, 409)
        rejected.close()
        response = json.loads(self.post_json('/command', {'command': 'scene safe_scene'}).read())
        self.assertTrue(response['ok'])
        self.assertTrue(bridge.validate_game_command('act 1', {'ch0_main'}))
        self.assertFalse(bridge.validate_game_command('act 2', {'ch0_main'}))
        self.assertFalse(bridge.validate_game_command('scene label; quit()', {'ch0_main'}))
        with self.assertRaises(urllib.error.HTTPError) as invalid_command:
            self.post_json('/command', {'command': 'run DDLC.sh'})
        self.assertEqual(invalid_command.exception.code, 400)
        invalid_command.exception.close()

    def test_recommended_status_reports_missing_game_and_headless_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            status = bridge.recommended_status(directory)
            self.assertFalse(status['ready'])
            self.assertIn('game/scripts.rpa', status['missing'])
            started, message = bridge.launch_recommended_game(directory)
            self.assertFalse(started)
            self.assertIn('Missing/incompatible', message)

    def test_private_installer_and_no_overwrite(self):
        entries = [
            ('DDLC-1.1.1-pc/DDLC.sh', '#!/bin/sh\n'),
            ('DDLC-1.1.1-pc/DDLC.exe', 'windows launcher'),
            ('DDLC-1.1.1-pc/game/scripts.rpa', 'RPA-3.0 fixture'),
            ('DDLC-1.1.1-pc/lib/linux-x86_64/DDLC', 'linux runtime'),
            ('DDLC-1.1.1-pc/lib/windows-i686/DDLC.exe', 'windows runtime'),
            ('DDLC-1.1.1-pc/renpy/__init__.pyo', b"Ren'Py 6.99.12.3"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'private.zip'
            archive.write_bytes(self.make_zip(entries))
            patch_source = root / 'bridge.rpy'
            patch_source.write_text('patch fixture', encoding='utf-8')
            destination = root / 'installed' / 'DDLC-1.1.1-pc'
            status = bridge.install_recommended_game(archive, destination, patch_source)
            self.assertTrue(status['ready'])
            self.assertEqual(status['runtime_version'], '6.99.12.3')
            self.assertEqual((destination / 'game/ddlc_control_centre.rpy').read_text(), 'patch fixture')
            with self.assertRaises(FileExistsError):
                bridge.install_recommended_game(archive, destination, patch_source)

    def test_invalid_runtime_label_is_not_advertised_to_game(self):
        self.assertFalse(bridge.validate_game_command('scene nonexistent', {'ch0_main'}))
        self.assertFalse(bridge.validate_game_command('act 4', {'ch0_main', 'ch21_main'}))


if __name__ == '__main__':
    unittest.main()
