# trace: NFR-US-01, NFR-US-02, NFR-US-06, NFR-PF-03
"""結合試験の共通部品：開発環境の PC にインストール済みのブラウザ（Microsoft Edge・Google Chrome）の操作。

- ブラウザをヘッドレスで起動し、Chrome DevTools Protocol（CDP）で画面の表示・フォームの送信・確認ダイアログの承諾・
  表示領域の設定・Navigation Timing の取得を行う（標準ライブラリだけで WebSocket を扱う。追加の依存を持たない）。
- プロファイルは試験ごとの一時ディレクトリに作り、終了時にプロセスを停止して削除する。
- 背景通信（同期・更新確認・翻訳等）は起動オプションで止める。画面が要求した
  URL は記録し、試験側で同一オリジンかを判定する。
本ファイルは業務判定・期待値を持たない（判定は各 test_it_*.py）。
"""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

CANDIDATES = {
    "edge": (
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ),
    "chrome": (
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ),
}

_FLAGS = (
    "--headless=new",
    "--remote-debugging-port=0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-sync",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-client-side-phishing-detection",
    "--no-pings",
    "--metrics-recording-only",
    "--safebrowsing-disable-auto-update",
    "--disable-features=Translate,OptimizationHints,MediaRouter,AutofillServerCommunication,msEdgeShopping",
    "--window-size=1280,720",
    "--force-device-scale-factor=1",
)

LAYOUT_JS = r"""
(() => {
  const de = document.documentElement;
  const vw = de.clientWidth;
  const over = [];
  for (const el of document.body.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.right > vw + 0.5 || r.left < -0.5) over.push(el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''));
  }
  return JSON.stringify({
    scrollWidth: de.scrollWidth, clientWidth: vw, innerWidth: window.innerWidth, innerHeight: window.innerHeight,
    bodyScrollWidth: document.body.scrollWidth, overflowElements: over.slice(0, 20), overflowCount: over.length,
    title: document.title, lang: de.lang, charset: document.characterSet, url: location.href
  });
})()
"""

TIMING_JS = r"""
(() => {
  const n = performance.getEntriesByType('navigation')[0];
  if (!n || !n.loadEventEnd) return null;
  const resources = performance.getEntriesByType('resource').map(r => r.name);
  return JSON.stringify({display_complete_ms: n.loadEventEnd - n.startTime,
                         response_end_ms: n.responseEnd - n.startTime,
                         dom_content_loaded_ms: n.domContentLoadedEventEnd - n.startTime, type: n.type, resources});
})()
"""


# trace: NFR-US-01, NFR-US-06, NFR-PF-03
def executable(name):
    """インストール済みのブラウザの実行ファイル（見つからなければ None）。"""
    for candidate in CANDIDATES[name]:
        if Path(candidate).is_file():
            return candidate
    return None


# trace: NFR-US-01, NFR-US-06, NFR-PF-03
def file_version(path):
    """実行ファイルの製品バージョン（Windows のバージョン情報。PowerShell で読む）。"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"(Get-Item '{path}').VersionInfo.ProductVersion"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return completed.stdout.strip() or None


# trace: NFR-US-06
def windows_info():
    """OS の種類・ビルド番号（Windows 11 はビルド 22000 以上）。"""
    if sys.platform != "win32":
        return {"platform": sys.platform}
    version = sys.getwindowsversion()
    import platform

    return {
        "platform": "win32",
        "build": version.build,
        "major": version.major,
        "edition": platform.win32_edition(),
        "release": platform.release(),
        "is_windows_11": version.major == 10 and version.build >= 22000,
    }


# trace: NFR-US-01, NFR-PF-03
class _WebSocket:
    """RFC 6455 の最小限のクライアント（テキストフレーム・分割・ping/pong・close）。"""

    def __init__(self, url, timeout=30):
        assert url.startswith("ws://"), url
        hostport, _, path = url[5:].partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        buffer = bytearray()
        while b"\r\n\r\n" not in buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("websocket handshake failed")
            buffer += chunk
        head, _, rest = bytes(buffer).partition(b"\r\n\r\n")
        status = head.split(b"\r\n", 1)[0]
        if b" 101 " not in status + b" ":
            raise ConnectionError(status.decode("latin-1"))
        self._buffer = bytearray(rest)
        self.sock.settimeout(None)
        self._lock = threading.Lock()

    def _read(self, size):
        while len(self._buffer) < size:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("websocket closed")
            self._buffer += chunk
        data = bytes(self._buffer[:size])
        del self._buffer[:size]
        return data

    def send(self, payload, opcode=0x1):
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        header = bytearray([0x80 | opcode])
        size = len(data)
        if size < 126:
            header.append(0x80 | size)
        elif size < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", size)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", size)
        mask = os.urandom(4)
        header += mask
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
        with self._lock:
            self.sock.sendall(bytes(header) + masked)

    def recv(self):
        message = bytearray()
        while True:
            first, second = self._read(2)
            size = second & 0x7F
            if size == 126:
                size = struct.unpack("!H", self._read(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self._read(8))[0]
            mask = self._read(4) if second & 0x80 else None
            data = self._read(size)
            if mask:
                data = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
            opcode = first & 0x0F
            if opcode == 0x8:
                return None
            if opcode == 0x9:
                self.send(data, 0xA)
                continue
            if opcode == 0xA:
                continue
            message += data
            if first & 0x80:
                return message.decode("utf-8")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


# trace: NFR-US-01, NFR-PF-03
class BrowserError(AssertionError):
    pass


# trace: NFR-US-01, NFR-US-02, NFR-US-06, NFR-PF-03
class Browser:
    """ヘッドレスのブラウザ1つ（タブ1つ）。表示領域は 1280×720・表示倍率 100%。"""

    def __init__(self, name, *, width=1280, height=720, disable_cache=False):
        path = executable(name)
        if path is None:
            raise BrowserError(f"{name} がインストールされていない")
        self.name = name
        self.path = path
        self.profile = tempfile.mkdtemp(prefix=f"mc-it-{name}-")
        self.proc = subprocess.Popen(
            [path, *_FLAGS, f"--user-data-dir={self.profile}", "about:blank"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._cv = threading.Condition()
        self._events = []
        self._responses = {}
        self._next_id = 0
        self._closed = False
        self.dialogs = []
        try:
            port = self._port()
            self.version = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=30))
            page = next(
                t
                for t in json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=30))
                if t.get("type") == "page"
            )
            self.ws = _WebSocket(page["webSocketDebuggerUrl"])
            threading.Thread(target=self._reader, daemon=True).start()
            for method in ("Page.enable", "Network.enable", "Runtime.enable", "Log.enable"):
                self.call(method)
            self.call(
                "Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False
            )
            if disable_cache:
                self.call("Network.setCacheDisabled", cacheDisabled=True)
        except Exception:
            self.close()
            raise

    def _port(self):
        marker = Path(self.profile) / "DevToolsActivePort"
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if marker.is_file():
                lines = marker.read_text(encoding="ascii").splitlines()
                if lines and lines[0].strip().isdigit():
                    return int(lines[0])
            if self.proc.poll() is not None:
                raise BrowserError(f"{self.name} が起動直後に終了した（終了コード {self.proc.returncode}）")
            time.sleep(0.1)
        raise BrowserError(f"{self.name} の DevTools の待受けが始まらない")

    def _new_id(self):
        with self._cv:
            self._next_id += 1
            return self._next_id

    def _reader(self):
        while True:
            try:
                raw = self.ws.recv()
            except (OSError, ConnectionError):
                raw = None
            if raw is None:
                with self._cv:
                    self._closed = True
                    self._cv.notify_all()
                return
            message = json.loads(raw)
            if message.get("method") == "Page.javascriptDialogOpening":
                # 確認ダイアログ（data-confirm）は承諾する。表示された文言を記録する
                self.dialogs.append(message["params"].get("message"))
                self.ws.send(
                    json.dumps(
                        {"id": self._new_id(), "method": "Page.handleJavaScriptDialog", "params": {"accept": True}}
                    )
                )
            with self._cv:
                if "id" in message:
                    self._responses[message["id"]] = message
                else:
                    self._events.append(message)
                self._cv.notify_all()

    def call(self, method, timeout=60, **params):
        mid = self._new_id()
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        deadline = time.monotonic() + timeout
        with self._cv:
            while mid not in self._responses:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self._closed:
                    raise BrowserError(f"{self.name}: {method} の応答がない")
                self._cv.wait(remaining)
            message = self._responses.pop(mid)
        if "error" in message:
            raise BrowserError(f"{self.name}: {method}: {message['error']}")
        return message.get("result", {})

    def evaluate(self, expression, timeout=60):
        result = self.call("Runtime.evaluate", timeout=timeout, expression=expression, returnByValue=True)
        if "exceptionDetails" in result:
            raise BrowserError(f"{self.name}: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    def mark(self):
        with self._cv:
            return len(self._events)

    def events(self, since=0):
        with self._cv:
            return list(self._events[since:])

    def wait_event(self, method, since, timeout=60):
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                for event in self._events[since:]:
                    if event.get("method") == method:
                        return event
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self._closed:
                    raise BrowserError(f"{self.name}: {method} を待つ間にタイムアウト")
                self._cv.wait(remaining)

    def open(self, url, timeout=60):
        """画面を表示し（読込完了まで待つ）、表示結果を返す。"""
        since = self.mark()
        self.call("Page.navigate", url=url)
        self.wait_event("Page.loadEventFired", since, timeout)
        return self.report(since)

    def submit(self, selector, values=None, timeout=60):
        """フォームに値を入れ、ブラウザ自身の送信（requestSubmit：submit イベント・確認ダイアログを経る）を行う。"""
        since = self.mark()
        script = (
            "(() => { const f = document.querySelector(__SELECTOR__); if (!f) return 'no-form';"
            " const v = __VALUES__; for (const k of Object.keys(v)) { const el = f.elements[k];"
            " if (!el) return 'no-field:' + k; el.value = v[k]; }"
            " f.requestSubmit(); return 'submitted'; })()"
        )
        script = script.replace("__SELECTOR__", json.dumps(selector)).replace(
            "__VALUES__", json.dumps(values or {}, ensure_ascii=False)
        )
        state = self.evaluate(script, timeout=timeout)
        if state != "submitted":
            raise BrowserError(f"{self.name}: {selector}: {state}")
        self.wait_event("Page.loadEventFired", since, timeout)
        return self.report(since)

    def timing(self, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = self.evaluate(TIMING_JS)
            if value:
                return json.loads(value)
            time.sleep(0.01)
        raise BrowserError(f"{self.name}: Navigation Timing の loadEventEnd が得られない")

    def report(self, since):
        """since 以降の表示の結果（主文書の応答・資源の応答と失敗・スクリプトの例外・コンソールのエラー・配置）。"""
        events = self.events(since)
        documents, resources, failures, requested, errors = [], [], [], [], []
        for event in events:
            method, params = event.get("method"), event.get("params", {})
            if method == "Network.requestWillBeSent":
                requested.append(params["request"]["url"])
            elif method == "Network.responseReceived":
                row = {"url": params["response"]["url"], "status": params["response"]["status"], "type": params["type"]}
                (documents if params["type"] == "Document" else resources).append(row)
            elif method == "Network.loadingFailed":
                failures.append({"type": params.get("type"), "error": params.get("errorText")})
            elif method == "Runtime.exceptionThrown":
                errors.append(
                    {"kind": "exception", "text": json.dumps(params.get("exceptionDetails"), ensure_ascii=False)}
                )
            elif method == "Runtime.consoleAPICalled" and params.get("type") in ("error", "assert"):
                errors.append({"kind": "console", "text": json.dumps(params.get("args"), ensure_ascii=False)})
            elif method == "Log.entryAdded" and params.get("entry", {}).get("level") == "error":
                entry = params["entry"]
                errors.append({"kind": "log", "text": entry.get("text"), "url": entry.get("url")})
        layout = json.loads(self.evaluate(LAYOUT_JS))
        return {
            "document": documents[-1] if documents else None,
            "resources": resources,
            "failures": failures,
            "requested": requested,
            "errors": errors,
            "layout": layout,
        }

    def close(self):
        ws = getattr(self, "ws", None)
        if ws is not None:
            ws.close()
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=20)
        for _ in range(20):
            try:
                shutil.rmtree(self.profile)
                break
            except OSError:
                time.sleep(0.25)
