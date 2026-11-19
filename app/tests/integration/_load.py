# trace: NFR-PF-04, NFR-PF-05, NFR-PF-11, NFR-PF-14, NFR-PF-15
"""結合試験の共通部品：開発環境（ENV-01 相当の1台の PC）での小規模の負荷の発生と、応答時間・資源使用量の記録。

- 仮想利用者は HTTP で live_server（Django
  の試験用サーバー。Gunicorn ではない）へ要求を送る。思考時間は要求ごとに乱数で与える。
- 応答時間は要求の送信から応答本文の受信完了までの時間（負荷の発生元が同じ PC のため、その処理時間を含む：DIF-09）。
- 資源使用量は、アプリケーションのプロセス（試験プロセス：live_server
  と負荷の発生元を含む）の CPU 時間・ワーキングセットと、
  データベースのコンテナの docker stats を一定間隔で記録する（参考値）。
本ファイルは業務判定・期待値を持たない（判定は各 test_it_*.py）。
"""

import http.client
import json
import math
import os
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit


# trace: NFR-PF-04, NFR-PF-05, NFR-PF-11, NFR-PF-15
def p95(values):
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


# trace: NFR-PF-04, NFR-PF-05, NFR-PF-11, NFR-PF-15
class Recorder:
    """要求ごとの (開始時刻, 種別, 区分, 状態コード, 応答時間) を記録する（スレッド間で共有）。"""

    def __init__(self):
        self.started = time.monotonic()
        self.samples = []
        self._lock = threading.Lock()

    def add(self, kind, group, status, elapsed, at):
        with self._lock:
            self.samples.append(
                {"at": at - self.started, "kind": kind, "group": group, "status": status, "elapsed": elapsed}
            )

    def snapshot(self):
        with self._lock:
            return list(self.samples)


# trace: NFR-PF-04, NFR-PF-05, NFR-PF-11, NFR-PF-15
class HttpUser:
    """1人の仮想利用者の HTTP クライアント（JSON 本文・Bearer）。接続に失敗した要求は状態コード 0 として記録する。"""

    def __init__(self, base_url, recorder, timeout=60):
        parts = urlsplit(base_url)
        self.host, self.port = parts.hostname, parts.port
        self.recorder = recorder
        self.timeout = timeout
        self.token = None

    def request(self, kind, group, method, path, data=None, token=None, raw=False):
        headers = {"Accept": "application/json" if not raw else "text/html"}
        payload = None
        if data is not None:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        bearer = token or self.token
        if bearer and not raw:
            headers["Authorization"] = bearer
        start = time.monotonic()
        status, body = 0, None
        try:
            connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            try:
                connection.request(method.upper(), path, body=payload, headers=headers)
                response = connection.getresponse()
                content = response.read()
                status = response.status
                if not raw and content:
                    try:
                        body = json.loads(content.decode("utf-8"))
                    except ValueError:
                        body = None
            finally:
                connection.close()
        except OSError:
            status = 0
        elapsed = time.monotonic() - start
        self.recorder.add(kind, group, status, elapsed, start)
        return status, body


# trace: NFR-PF-14, NFR-PF-15
def _working_set_bytes():
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class _Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = _Counters()
    counters.cb = ctypes.sizeof(_Counters)
    kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return None
    return int(counters.WorkingSetSize)


# trace: NFR-PF-14
def _physical_memory_bytes():
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class _Status(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _Status()
    status.dwLength = ctypes.sizeof(_Status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPhys)


# trace: NFR-PF-14, NFR-PF-15
def _docker_stats(container):
    completed = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", container],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    row = json.loads(completed.stdout.strip().splitlines()[0])
    return {
        "cpu_percent": float(row["CPUPerc"].rstrip("%")),
        "mem_percent": float(row["MemPerc"].rstrip("%")),
        "mem_usage": row["MemUsage"],
    }


# trace: NFR-PF-14, NFR-PF-15
class ResourceSampler(threading.Thread):
    """一定間隔でアプリケーションのプロセスとデータベースのコンテナの資源使用量を記録する（参考値）。"""

    def __init__(self, container, interval=10.0):
        super().__init__(daemon=True)
        self.container = container
        self.interval = interval
        self.samples = []
        self._stop_event = threading.Event()
        self.cpu_count = os.cpu_count() or 1
        self.physical_memory = _physical_memory_bytes()

    def _sample(self, previous):
        now = time.monotonic()
        times = os.times()
        cpu = times.user + times.system
        row = {"at": None, "app_working_set_bytes": _working_set_bytes(), "db": _docker_stats(self.container)}
        if previous is not None:
            wall = now - previous[0]
            used = cpu - previous[1]
            row["app_cpu_cores_used"] = round(used / wall, 3) if wall > 0 else None
            row["app_cpu_percent_of_host"] = round(used / wall / self.cpu_count * 100, 2) if wall > 0 else None
        return row, (now, cpu)

    def run(self):
        start = time.monotonic()
        _, previous = self._sample(None)
        while not self._stop_event.wait(self.interval):
            row, previous = self._sample(previous)
            row["at"] = round(time.monotonic() - start, 1)
            self.samples.append(row)

    def stop(self):
        self._stop_event.set()
        self.join(timeout=120)
        return self.samples


# trace: NFR-PF-04, NFR-PF-05, NFR-PF-11, NFR-PF-15
def summarize(samples):
    """区分・種別ごとの件数・95パーセンタイル・最大・状態コードの分布。"""
    groups = {}
    for row in samples:
        for key in (row["group"], f"{row['group']}.{row['kind']}"):
            groups.setdefault(key, []).append(row)
    result = {}
    for key, rows in sorted(groups.items()):
        elapsed = [r["elapsed"] for r in rows]
        statuses = {}
        for r in rows:
            statuses[str(r["status"])] = statuses.get(str(r["status"]), 0) + 1
        result[key] = {
            "requests": len(rows),
            "p95_seconds": round(p95(elapsed), 4),
            "max_seconds": round(max(elapsed), 4),
            "statuses": statuses,
        }
    return result
