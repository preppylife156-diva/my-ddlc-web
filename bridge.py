#!/usr/bin/env python3
<<<<<<< HEAD
"""Loopback package host and command bridge for the DDLC Control Centre."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, unquote, urlparse
import atexit
import json
import mimetypes
import os
import platform
import pickle
import pickletools
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
import zlib

HOST, PORT = '127.0.0.1', 8765
PROJECT_ROOT = Path(__file__).resolve().parent
TOKEN_FILE = Path(os.environ.get('DDLC_CC_TOKEN_FILE', Path.home() / '.ddlc-control-centre-token'))
GAME_ARCHIVE = Path(os.environ.get('DDLC_ARCHIVE', PROJECT_ROOT / 'ddlc-win.zip'))
RECOMMENDED_GAME_DIR = Path(os.environ.get('DDLC_GAME_DIR', PROJECT_ROOT / 'private-game' / 'DDLC-1.1.1-pc'))
MAX_UPLOAD = 512 * 1024 * 1024
MAX_EXTRACTED = 1024 * 1024 * 1024
MAX_FILES = 20000
MAX_RESULT = 65536


def load_or_create_token():
    try:
        token = TOKEN_FILE.read_text(encoding='ascii').strip()
        if len(token) >= 32:
            try:
                TOKEN_FILE.chmod(0o600)
            except OSError:
                pass
            return token
    except FileNotFoundError:
        pass
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    try:
        descriptor = os.open(str(TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='ascii') as output:
            output.write(token + '\n')
    except FileExistsError:
        token = TOKEN_FILE.read_text(encoding='ascii').strip()
        if len(token) < 32:
            raise RuntimeError('bridge token file is invalid')
    return token


TOKEN = load_or_create_token()
queue = []
results = []
next_id = 1
last_game_seen = 0.0
runtime_labels = set()
active_package = None
game_process = None
lock = threading.Lock()
ACT_LABELS = {'act 1': 'ch0_main', 'act 2': 'ch21_main', 'act 3': 'ch30_main', 'act 4': 'ch40_main'}


def allowed_origin(origin):
    if not origin:
        return True
    if origin == 'null':
        return False
    if origin in ('http://127.0.0.1:8765', 'http://localhost:8765'):
        return True
    codespace_origin = 'https://%s-%d.app.github.dev' % (os.environ.get('CODESPACE_NAME', ''), PORT)
    return bool(os.environ.get('CODESPACE_NAME')) and origin == codespace_origin


def game_connected():
    return time.time() - last_game_seen < 4.0


def _extract_archive(archive):
    root = Path(tempfile.mkdtemp(prefix='ddlc-control-centre-'))
    files = []
    total = 0
    try:
        infos = archive.infolist()
        if len(infos) > MAX_FILES:
            raise ValueError('archive contains too many entries')
        seen = set()
        for info in infos:
            name = info.filename
            if '\\' in name or '\x00' in name:
                raise ValueError('archive contains an unsafe path')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('archive contains an unsafe path')
            if not path.parts:
                continue
            mode = (info.external_attr >> 16) & 0xffff
            if stat.S_ISLNK(mode):
                raise ValueError('symbolic links are not supported')
            file_type = stat.S_IFMT(mode)
            if file_type and file_type not in (stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('special ZIP entries are not supported')
            if info.flag_bits & 1:
                raise ValueError('encrypted ZIP entries are not supported')
            destination = root.joinpath(*path.parts)
            if os.path.commonpath((str(root.resolve()), str(destination.resolve()))) != str(root.resolve()):
                raise ValueError('archive contains an unsafe path')
            if info.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            normalized = '/'.join(path.parts)
            if normalized in seen:
                raise ValueError('archive contains duplicate file paths')
            seen.add(normalized)
            if info.file_size > MAX_EXTRACTED or total + info.file_size > MAX_EXTRACTED:
                raise ValueError('archive expands beyond the 1 GiB safety limit')
            if len(files) >= MAX_FILES:
                raise ValueError('archive contains too many files')
            destination.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with archive.open(info) as source, destination.open('xb') as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > info.file_size or written > MAX_EXTRACTED:
                        raise ValueError('ZIP entry exceeds its declared size')
                    target.write(chunk)
            if written != info.file_size:
                raise ValueError('ZIP entry size did not match its directory')
            total += written
            files.append(normalized)
=======
"""Local-only bridge between the DDLC Control Centre HTML and the Ren'Py patch."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path, PurePosixPath
from io import BytesIO
import atexit, json, mimetypes, os, re, shutil, stat, tempfile, time, threading, zipfile, secrets
HOST, PORT = '127.0.0.1', 8765
_codespace_name=os.environ.get('CODESPACE_NAME','')
TOKEN = 'ddlc-control-centre-local-v1'
queue=[]; results=[]; next_id=1; last_game_seen=0.0
lock=threading.Lock()

def game_connected(): return time.time()-last_game_seen < 4.0
MAX_UPLOAD=512*1024*1024
MAX_EXTRACTED=1024*1024*1024
MAX_FILES=20000
active_package=None

def allowed_origin(origin):
    if not origin: return True
    if origin == 'null': return False
    if origin in ('http://127.0.0.1:8765','http://localhost:8765'): return True
    codespace_origin='https://%s-%d.app.github.dev' % (_codespace_name, PORT)
    return bool(_codespace_name) and origin == codespace_origin

def extract_package(raw):
    root=Path(tempfile.mkdtemp(prefix='ddlc-control-centre-'))
    files=[]
    total=0
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            infos=archive.infolist()
            if len(infos)>MAX_FILES: raise ValueError('archive contains too many entries')
            seen=set()
            for info in infos:
                name=info.filename
                if '\\' in name or '\x00' in name: raise ValueError('archive contains an unsafe path')
                path=PurePosixPath(name)
                if path.is_absolute() or '..' in path.parts: raise ValueError('archive contains an unsafe path')
                if not path.parts: continue
                mode=(info.external_attr >> 16) & 0xffff
                if stat.S_ISLNK(mode): raise ValueError('symbolic links are not supported')
                if info.flag_bits & 1: raise ValueError('encrypted ZIP entries are not supported')
                destination=root.joinpath(*path.parts)
                if os.path.commonpath((str(root.resolve()), str(destination.resolve()))) != str(root.resolve()):
                    raise ValueError('archive contains an unsafe path')
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                normalized='/'.join(path.parts)
                if normalized in seen: raise ValueError('archive contains duplicate file paths')
                seen.add(normalized)
                if info.file_size > MAX_EXTRACTED or total + info.file_size > MAX_EXTRACTED:
                    raise ValueError('archive expands beyond the 1 GiB safety limit')
                if len(files) >= MAX_FILES: raise ValueError('archive contains too many files')
                destination.parent.mkdir(parents=True, exist_ok=True)
                written=0
                with archive.open(info) as source, destination.open('xb') as target:
                    while True:
                        chunk=source.read(1024*1024)
                        if not chunk: break
                        written+=len(chunk)
                        if written > info.file_size or written > MAX_EXTRACTED:
                            raise ValueError('ZIP entry exceeds its declared size')
                        target.write(chunk)
                if written != info.file_size: raise ValueError('ZIP entry size did not match its directory')
                total+=written
                files.append(normalized)
>>>>>>> origin/main
        return root, files
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise

<<<<<<< HEAD

def extract_package(raw):
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        return _extract_archive(archive)


def validate_game_command(command, available_labels=None):
    available_labels = set(available_labels or ())
    if command in ('reset', 'restart-game', 'scene list', 'scene current'):
        return True
    if command in ACT_LABELS:
        return ACT_LABELS[command] in available_labels
    match = re.fullmatch(r'scene ([A-Za-z_][A-Za-z0-9_.]{0,119})', command)
    return bool(match and match.group(1) in available_labels)


def package_file(package_id, relative_path):
    with lock:
        current = active_package
    if not current or current['id'] != package_id:
        return None
    path = PurePosixPath(relative_path)
    if path.is_absolute() or not path.parts or any(part in ('', '.', '..') for part in path.parts):
        return None
    root = current['root']
    target = root.joinpath(*path.parts)
    if os.path.commonpath((str(root.resolve()), str(target.resolve()))) != str(root.resolve()):
        return None
    return target if target.is_file() and not target.is_symlink() else None


def recommended_status(game_dir=None):
    game_dir = Path(game_dir or RECOMMENDED_GAME_DIR)
    required = ['DDLC.sh', 'DDLC.exe', 'game/scripts.rpa', 'game/ddlc_control_centre.rpy', 'renpy/__init__.pyo']
    missing = [name for name in required if not (game_dir / name).is_file()]
    machine = platform.machine().lower()
    if sys.platform.startswith('linux'):
        launcher = game_dir / 'DDLC.sh'
        if machine in ('x86_64', 'amd64'):
            runtime = 'lib/linux-x86_64/DDLC'
        elif machine in ('i386', 'i486', 'i586', 'i686', 'x86'):
            runtime = 'lib/linux-i686/DDLC'
        else:
            runtime = None
        if runtime and not (game_dir / runtime).is_file():
            missing.append(runtime)
        platform_supported = runtime is not None
        has_display = bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
        platform_reason = '' if not platform_supported else ('No graphical display is available in this session.' if not has_display else '')
    elif os.name == 'nt':
        launcher = game_dir / 'DDLC.exe'
        platform_supported = True
        has_display = True
        platform_reason = ''
        if not (game_dir / 'lib/windows-i686/DDLC.exe').is_file():
            missing.append('lib/windows-i686/DDLC.exe')
    else:
        launcher = game_dir / 'DDLC.sh'
        platform_supported = False
        has_display = False
        platform_reason = 'The supplied ZIP has Windows and Linux runtimes, not a native runtime for this operating system.'
    version = 'unknown'
    metadata = game_dir / 'renpy/__init__.pyo'
    if metadata.is_file():
        match = re.search(rb'(?<![0-9])(?:6|7|8)\.[0-9]{1,2}\.[0-9]{1,2}(?:\.[0-9]+)?', metadata.read_bytes())
        if match:
            version = match.group(0).decode('ascii')
    return {
        'game_dir': str(game_dir), 'missing': missing, 'runtime_version': version,
        'platform_supported': platform_supported, 'has_display': has_display,
        'ready': not missing and platform_supported,
        'launchable': not missing and platform_supported and has_display,
        'platform_reason': platform_reason, 'launcher': str(launcher),
    }


def install_recommended_game(archive_path=None, destination=None, patch_source=None):
    archive_path = Path(archive_path or GAME_ARCHIVE)
    destination = Path(destination or RECOMMENDED_GAME_DIR)
    patch_source = Path(patch_source or PROJECT_ROOT / 'ddlc_control_centre.rpy')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError('refusing to overwrite existing game directory: ' + str(destination))
    if not archive_path.is_file():
        raise FileNotFoundError('private game ZIP not found: ' + str(archive_path))
    if not patch_source.is_file():
        raise FileNotFoundError('Ren\'Py integration patch not found: ' + str(patch_source))
    size = archive_path.stat().st_size
    if size <= 0 or size > MAX_UPLOAD:
        raise ValueError('game ZIP must be no larger than 512 MiB')
    root = None
    try:
        with zipfile.ZipFile(archive_path) as archive:
            root, _files = _extract_archive(archive)
        source = root / 'DDLC-1.1.1-pc'
        if not source.is_dir():
            raise ValueError('ZIP does not contain the verified DDLC-1.1.1-pc package root')
        required = ('DDLC.sh', 'DDLC.exe', 'game/scripts.rpa', 'lib/linux-x86_64/DDLC', 'lib/windows-i686/DDLC.exe', 'renpy/__init__.pyo')
        missing = [name for name in required if not (source / name).is_file()]
        if missing:
            raise ValueError('game ZIP is missing required files: ' + ', '.join(missing))
        patch_target = source / 'game/ddlc_control_centre.rpy'
        if patch_target.exists():
            raise FileExistsError('game ZIP already contains the patch path; refusing to overwrite it')
        shutil.copyfile(str(patch_source), str(patch_target))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return recommended_status(destination)
    finally:
        if root:
            shutil.rmtree(root, ignore_errors=True)


def launch_recommended_game(game_dir=None):
    global game_process
    status = recommended_status(game_dir)
    if not status['ready']:
        missing = ', '.join(status['missing']) or status['platform_reason']
        return False, 'Recommended game is not ready. Missing/incompatible: ' + missing
    if not status['launchable']:
        return False, status['platform_reason'] or 'No compatible graphical runtime is available on this device.'
    with lock:
        if game_process is not None and game_process.poll() is None:
            return True, 'Game process is already running; waiting for the Ren\'Py bridge heartbeat.'
    try:
        if os.name == 'nt':
            process = subprocess.Popen([status['launcher']], cwd=status['game_dir'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            process = subprocess.Popen(['/bin/sh', status['launcher']], cwd=status['game_dir'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        return False, 'Could not start the Ren\'Py launcher: ' + str(error)
    with lock:
        game_process = process
    return True, 'Ren\'Py launch requested (PID %s); waiting for the game patch to connect.' % process.pid


def cleanup_package():
    global active_package
    with lock:
        package = active_package
        active_package = None
    if package:
        shutil.rmtree(package['root'], ignore_errors=True)


atexit.register(cleanup_package)


class Handler(BaseHTTPRequestHandler):
    server_version = 'DDLCControlBridge/2.0'

    def log_message(self, fmt, *args):
        print('[bridge]', fmt % args)

    def auth(self):
        query = parse_qs(urlparse(self.path).query)
        return query.get('token', [''])[0] == TOKEN and allowed_origin(self.headers.get('Origin'))

    def cors(self):
        origin = self.headers.get('Origin')
        if origin and allowed_origin(origin):
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def send(self, code, obj):
        data = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.cors()
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        if not allowed_origin(self.headers.get('Origin')):
            return self.send(403, {'ok': False, 'error': 'origin not allowed'})
        self.send_response(204)
        self.cors()
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.end_headers()

    def do_GET(self):
        global last_game_seen
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == '/':
            page = Path(__file__).with_name('ddlc-control-centre-integrated.html')
            try:
                data = page.read_bytes().replace(b'__DDLC_CC_TOKEN__', TOKEN.encode('ascii'))
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)
                return
            except OSError:
                return self.send(404, {'ok': False, 'error': 'Control Centre HTML file not found'})
        if parsed.path.startswith('/package/'):
            parts = parsed.path.split('/', 3)
            if len(parts) != 4:
                return self.send(404, {'ok': False, 'error': 'package file not found'})
            origin = self.headers.get('Origin')
            if origin and origin != 'null' and not allowed_origin(origin):
                return self.send(403, {'ok': False, 'error': 'origin not allowed'})
            target = package_file(parts[2], unquote(parts[3]))
            if not target:
                return self.send(404, {'ok': False, 'error': 'package file not found'})
            try:
                size = target.stat().st_size
                self.send_response(200)
                self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                self.send_header('Content-Length', str(size))
                if origin == 'null':
                    self.send_header('Access-Control-Allow-Origin', 'null')
                else:
                    self.cors()
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cross-Origin-Resource-Policy', 'cross-origin')
                self.end_headers()
                with target.open('rb') as source:
                    shutil.copyfileobj(source, self.wfile, 1024 * 1024)
                return
            except OSError:
                return self.send(404, {'ok': False, 'error': 'package file not found'})
        if not self.auth():
            return self.send(403, {'ok': False, 'error': 'bad token or origin'})
        if parsed.path == '/recommended':
            return self.send(200, {'ok': True, **recommended_status()})
        with lock:
            if parsed.path == '/status':
                running = game_process is not None and game_process.poll() is None
                return self.send(200, {'ok': True, 'bridge': True, 'game_connected': game_connected(), 'game_process_running': running, 'runtime_label_count': len(runtime_labels), 'queued': len(queue), 'last_game_seen': last_game_seen})
            if parsed.path == '/poll':
                last_game_seen = time.time()
                item = queue.pop(0) if queue else None
                return self.send(200, {'ok': True, 'command': item})
            if parsed.path == '/results':
                try:
                    after = int(query.get('after', ['0'])[0])
                except ValueError:
                    after = 0
                return self.send(200, {'ok': True, 'results': [result for result in results if result['id'] > after][-50:]})
        if parsed.path == '/result':
            return self.send(405, {'ok': False, 'error': 'POST required'})
        return self.send(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        global next_id, active_package, runtime_labels
        if not self.auth():
            return self.send(403, {'ok': False, 'error': 'bad token or origin'})
        route = urlparse(self.path).path
        if route == '/launch/recommended':
            started, message = launch_recommended_game()
            return self.send(202 if started else 409, {'ok': started, 'message': message, 'game_connected': game_connected()})
        if route == '/package':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > MAX_UPLOAD:
                    return self.send(413, {'ok': False, 'error': 'ZIP must be between 1 byte and 512 MiB'})
                raw = self.rfile.read(length)
                if len(raw) != length:
                    return self.send(400, {'ok': False, 'error': 'incomplete ZIP upload'})
                root, files = extract_package(raw)
                package = {'id': secrets.token_urlsafe(24), 'root': root, 'files': files}
                with lock:
                    previous = active_package
                    active_package = package
                if previous:
                    shutil.rmtree(previous['root'], ignore_errors=True)
                return self.send(200, {'ok': True, 'package_id': package['id'], 'files': files})
            except (zipfile.BadZipFile, ValueError, OSError, RuntimeError) as error:
                return self.send(400, {'ok': False, 'error': 'ZIP package rejected: ' + str(error)[:300]})
        if route == '/result':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > MAX_RESULT:
                    return self.send(413, {'ok': False, 'error': 'result request size is invalid'})
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                raw_labels = data.get('labels')
                labels = None
                if raw_labels is not None:
                    if not isinstance(raw_labels, list):
                        return self.send(400, {'ok': False, 'error': 'labels must be a list'})
                    labels = sorted(set(str(label) for label in raw_labels if isinstance(label, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]{0,119}', label)))[:2000]
                with lock:
                    if labels is not None:
                        runtime_labels = set(labels)
                    result = {'id': next_id, 'message': str(data.get('message', ''))[:1000], 'ok': bool(data.get('ok', False)), 'scene': data.get('scene')}
                    if labels is not None:
                        result['labels'] = labels
                    results.append(result)
                    if len(results) > 200:
                        del results[:-200]
                    next_id += 1
                return self.send(200, {'ok': True})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
                return self.send(400, {'ok': False, 'error': 'invalid result'})
        if route != '/command':
            return self.send(404, {'ok': False, 'error': 'not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 8192:
                return self.send(413, {'ok': False, 'error': 'command request size is invalid'})
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            command = str(data.get('command', '')).strip()
            if not command or len(command) > 200:
                return self.send(400, {'ok': False, 'error': 'invalid command'})
            with lock:
                available = set(runtime_labels) if game_connected() else set()
                if not validate_game_command(command, available):
                    if command.startswith('scene ') or command in ACT_LABELS:
                        return self.send(409, {'ok': False, 'error': 'scene command rejected: target is not in the current runtime label list; run scene list while the game patch is connected'})
                    return self.send(400, {'ok': False, 'error': 'command not permitted through game bridge'})
                item = {'id': next_id, 'command': command, 'created': time.time()}
                next_id += 1
                queue.append(item)
                connected = game_connected()
            return self.send(200, {'ok': True, 'id': item['id'], 'game_connected': connected, 'queued': not connected})
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return self.send(400, {'ok': False, 'error': 'invalid command request'})

    def do_DELETE(self):
        global active_package
        if not self.auth():
            return self.send(403, {'ok': False, 'error': 'bad token or origin'})
        package_id = urlparse(self.path).path.removeprefix('/package/')
        with lock:
            if not active_package or active_package['id'] != package_id:
                return self.send(404, {'ok': False, 'error': 'package session not found'})
            previous = active_package
            active_package = None
        shutil.rmtree(previous['root'], ignore_errors=True)
        return self.send(200, {'ok': True, 'removed': True})


def main():
    if sys.argv[1:] == ['--install-recommended']:
        status = install_recommended_game()
        print(json.dumps(status, indent=2))
        return
    if sys.argv[1:] == ['--check-recommended']:
        print(json.dumps(recommended_status(), indent=2))
        return
    print('DDLC Control Centre bridge listening only on http://127.0.0.1:%d' % PORT)
    print('Open its forwarded port for the UI. Ctrl+C stops the local bridge.')
    HTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nBridge stopped.')
=======
def validate_game_command(command):
    if command in ('reset','restart-game','scene list','scene current'):
        return True
    return command in ('act 1','act 2','act 3','act 4') or bool(re.fullmatch(r'scene [A-Za-z_][A-Za-z0-9_.]*', command))

def package_file(package_id, relative_path):
    with lock:
        current=active_package
    if not current or current['id'] != package_id: return None
    path=PurePosixPath(relative_path)
    if path.is_absolute() or not path.parts or any(part in ('', '.', '..') for part in path.parts): return None
    root=current['root']
    target=root.joinpath(*path.parts)
    if os.path.commonpath((str(root.resolve()), str(target.resolve()))) != str(root.resolve()): return None
    return target if target.is_file() else None

class Handler(BaseHTTPRequestHandler):
    server_version = 'DDLCControlBridge/1.0'
    def log_message(self, fmt, *args): print('[bridge]', fmt % args)
    def auth(self):
        q=parse_qs(urlparse(self.path).query)
        return q.get('token',[''])[0] == TOKEN and allowed_origin(self.headers.get('Origin'))
    def cors(self):
        origin=self.headers.get('Origin')
        if origin and allowed_origin(origin):
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Vary','Origin')
    def send(self, code, obj):
        data=json.dumps(obj).encode('utf-8')
        self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8')
        self.cors(); self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.send_header('Access-Control-Allow-Methods','GET, POST, DELETE, OPTIONS'); self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_OPTIONS(self):
        if not allowed_origin(self.headers.get('Origin')): return self.send(403,{'ok':False,'error':'origin not allowed'})
        self.send_response(204); self.cors(); self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.send_header('Access-Control-Allow-Methods','GET, POST, DELETE, OPTIONS'); self.end_headers()
    def do_GET(self):
        global last_game_seen
        u=urlparse(self.path); q=parse_qs(u.query)
        if u.path=='/':
            page=Path(__file__).with_name('ddlc-control-centre-integrated.html')
            try:
                data=page.read_bytes()
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
                self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store')
                self.end_headers(); self.wfile.write(data)
                return
            except OSError:
                return self.send(404,{'ok':False,'error':'Control Centre HTML file not found'})
        if u.path.startswith('/package/'):
            parts=u.path.split('/',3)
            if len(parts)!=4: return self.send(404,{'ok':False,'error':'package file not found'})
            target=package_file(parts[2], unquote(parts[3]))
            if not target: return self.send(404,{'ok':False,'error':'package file not found'})
            try:
                size=target.stat().st_size
                self.send_response(200)
                self.send_header('Content-Type',mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                self.send_header('Content-Length',str(size))
                if self.headers.get('Origin') == 'null':
                    self.send_header('Access-Control-Allow-Origin','null')
                else:
                    self.cors()
                self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cross-Origin-Resource-Policy','cross-origin')
                self.end_headers()
                with target.open('rb') as source: shutil.copyfileobj(source,self.wfile,1024*1024)
                return
            except OSError:
                return self.send(404,{'ok':False,'error':'package file not found'})
        if not self.auth(): return self.send(403,{'ok':False,'error':'bad token'})
        with lock:
            if u.path=='/status': return self.send(200,{'ok':True,'bridge':True,'game_connected':game_connected(),'queued':len(queue),'last_game_seen':last_game_seen})
            if u.path=='/poll':
                last_game_seen=time.time()
                item=queue.pop(0) if queue else None
                return self.send(200,{'ok':True,'command':item})
            if u.path=='/results':
                try: after=int(q.get('after',['0'])[0])
                except ValueError: after=0
                return self.send(200,{'ok':True,'results':[r for r in results if r['id']>after][-50:]})
            if u.path=='/result':
                return self.send(405,{'ok':False,'error':'POST required'})
        return self.send(404,{'ok':False,'error':'not found'})
    def do_POST(self):
        global next_id
        if not self.auth(): return self.send(403,{'ok':False,'error':'bad token'})
        route=urlparse(self.path).path
        if route=='/package':
            global active_package
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length<=0 or length>MAX_UPLOAD: return self.send(413,{'ok':False,'error':'ZIP must be between 1 byte and 512 MiB'})
                raw=self.rfile.read(length)
                if len(raw)!=length: return self.send(400,{'ok':False,'error':'incomplete ZIP upload'})
                root,files=extract_package(raw)
                package={'id':secrets.token_urlsafe(18),'root':root,'files':files}
                with lock:
                    previous=active_package
                    active_package=package
                if previous: shutil.rmtree(previous['root'],ignore_errors=True)
                return self.send(200,{'ok':True,'package_id':package['id'],'files':files})
            except (zipfile.BadZipFile, ValueError, OSError, RuntimeError) as e:
                return self.send(400,{'ok':False,'error':'ZIP package rejected: '+str(e)[:300]})
        if route=='/result':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if length>8192: return self.send(413,{'ok':False,'error':'request too large'})
                data=json.loads(self.rfile.read(length).decode('utf-8'))
                with lock:
                    results.append({'id':next_id,'message':str(data.get('message',''))[:1000],'ok':bool(data.get('ok',False)),'scene':data.get('scene')})
                    if len(results)>200: del results[:-200]
                    next_id += 1
                return self.send(200,{'ok':True})
            except Exception as e: return self.send(400,{'ok':False,'error':'invalid result'})
        if route!='/command': return self.send(404,{'ok':False,'error':'not found'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length>8192: return self.send(413,{'ok':False,'error':'request too large'})
            data=json.loads(self.rfile.read(length).decode('utf-8'))
            command=str(data.get('command','')).strip()
            if not command or len(command)>200: return self.send(400,{'ok':False,'error':'invalid command'})
            if not validate_game_command(command):
                return self.send(400,{'ok':False,'error':'command not permitted through game bridge'})
            with lock:
                item={'id':next_id,'command':command,'created':time.time()}; next_id+=1; queue.append(item)
                connected=game_connected()
            return self.send(200,{'ok':True,'id':item['id'],'game_connected':connected,'queued':not connected})
        except Exception as e: return self.send(400,{'ok':False,'error':'invalid request: '+str(e)})

    def do_DELETE(self):
        global active_package
        if not self.auth(): return self.send(403,{'ok':False,'error':'bad token'})
        package_id=urlparse(self.path).path.removeprefix('/package/')
        with lock:
            if not active_package or active_package['id']!=package_id:
                return self.send(404,{'ok':False,'error':'package session not found'})
            previous=active_package
            active_package=None
        shutil.rmtree(previous['root'],ignore_errors=True)
        return self.send(200,{'ok':True,'removed':True})

if __name__=='__main__':
    print('DDLC Control Centre bridge listening only on http://127.0.0.1:%d' % PORT)
    print('Keep this window open. Press Ctrl+C to stop. This bridge accepts only a small allowlist of game commands.')
    try: HTTPServer((HOST,PORT),Handler).serve_forever()
    except KeyboardInterrupt: print('\nBridge stopped.')
>>>>>>> origin/main
