import json
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import HTTPServer
from io import BytesIO

import bridge


class BridgePackageTests(unittest.TestCase):
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

    def request(self, path, data=None, method=None, content_type=None, origin=None):
        url = self.base + path + ('&' if '?' in path else '?') + 'token=' + bridge.TOKEN
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        if origin:
            headers['Origin'] = origin
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        return urllib.request.urlopen(request)

    def make_zip(self, entries):
        archive = BytesIO()
        with zipfile.ZipFile(archive, 'w') as output:
            for name, content in entries:
                output.writestr(name, content)
        return archive.getvalue()

    def test_serves_control_centre_and_checks_origins(self):
        page = self.request('/').read().decode('utf-8')
        self.assertIn('DDLC Control Centre', page)
        self.assertIn('id="runTypeBtn"', page)
        self.assertFalse(bridge.allowed_origin('null'))
        self.assertTrue(bridge.allowed_origin('http://127.0.0.1:8765'))
        with self.assertRaises(urllib.error.HTTPError) as blocked:
            self.request('/status', origin='https://untrusted.example')
        self.assertEqual(blocked.exception.code, 403)
        blocked.exception.close()

    def test_upload_and_serve_browser_package(self):
        raw = self.make_zip([('index.html', '<h1>Browser package</h1>'), ('assets/app.js', 'ok')])
        response = self.request('/package', raw, 'POST', 'application/zip')
        package = json.loads(response.read())
        self.assertEqual(package['files'], ['index.html', 'assets/app.js'])
        served = self.request('/package/%s/index.html' % package['package_id'])
        self.assertEqual(served.read(), b'<h1>Browser package</h1>')
        self.request('/package/%s' % package['package_id'], method='DELETE')
        with self.assertRaises(urllib.error.HTTPError) as missing:
            self.request('/package/%s/index.html' % package['package_id'])
        self.assertEqual(missing.exception.code, 404)
        missing.exception.close()

    def test_rejects_invalid_zip(self):
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.request('/package', b'not a zip archive', 'POST', 'application/zip')
        self.assertEqual(rejected.exception.code, 400)
        rejected.exception.close()

    def test_rejects_path_traversal(self):
        raw = self.make_zip([('../outside.txt', 'unsafe')])
        with self.assertRaises(urllib.error.HTTPError) as rejected:
            self.request('/package', raw, 'POST', 'application/zip')
        self.assertEqual(rejected.exception.code, 400)
        rejected.exception.close()

    def test_game_command_allowlist(self):
        self.assertTrue(bridge.validate_game_command('scene actual_label'))
        self.assertTrue(bridge.validate_game_command('act 2'))
        self.assertFalse(bridge.validate_game_command('scene label; quit()'))
        self.assertFalse(bridge.validate_game_command('run DDLC.sh'))


if __name__ == '__main__':
    unittest.main()
