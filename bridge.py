#!/usr/bin/env python3
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
        return root, files
    except Exception:
        shutil.rmtree(root, ignore_errors=True)
        raise

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
