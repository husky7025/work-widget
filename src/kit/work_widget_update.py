# -*- coding: utf-8 -*-
"""업무위젯 자동 업데이트 — GitHub 공개 저장소의 «최신 릴리스»에서 서명된 새 버전을 받아 키트 폴더에 덮어쓴다.

안전장치
- manifest.json 은 Ed25519 로 서명돼 있다. 비밀 열쇠는 만든 사람 PC(Windows 자격 증명 관리자)에만 있고,
  여기에는 공개 열쇠만 들어 있다 → GitHub 계정이 털려도 서명 없는 가짜 버전은 설치되지 않는다.
- app.zip 은 manifest 에 적힌 SHA-256 과 같아야 한다. 지금보다 «높은» 버전만 받는다 (옛 버전으로 되돌리기 공격 차단).
- 덮어쓰기 전에 지금 파일을 백업하고, 중간에 실패하면 되돌린다. .venv(파이썬)·크롬 프로필·설정·암호는 건드리지 않는다.
서명 검증은 순수 파이썬(RFC 8032)이라 추가 설치가 필요 없다.
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

PUBLIC_KEY_HEX = "__WORK_WIDGET_PUBKEY__"          # build.py 가 묶음을 만들 때 채운다
REPO = "husky7025/work-widget"
BASE_URL = os.environ.get("WORK_WIDGET_UPDATE_URL") or "https://github.com/%s/releases/latest/download/" % REPO
VERSION_FILE = "work_widget_version.json"
FLAG_FILE = ".work_widget_just_updated"
NO_WINDOW = 0x08000000

# ── Ed25519 (RFC 8032 참조 구현을 옮김) ──
_p = 2 ** 255 - 19
_d = -121665 * pow(121666, _p - 2, _p) % _p
_q = 2 ** 252 + 27742317777372353535851937790883648493
_sqrt_m1 = pow(2, (_p - 1) // 4, _p)


def _h(m):
    return hashlib.sha512(m).digest()


def _add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p
    D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _eq(P, Q):
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def _recover_x(y, sign):
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p)
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p:
        x = x * _sqrt_m1 % _p
    if (x * x - x2) % _p:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_gy = 4 * pow(5, _p - 2, _p) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _compress(P):
    zi = pow(P[2], _p - 2, _p)
    x, y = P[0] * zi % _p, P[1] * zi % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _p)


def _expand(seed):
    h = _h(seed)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key(seed):
    return _compress(_mul(_expand(seed)[0], _G))


def sign(seed, msg):
    a, prefix = _expand(seed)
    A = _compress(_mul(a, _G))
    r = int.from_bytes(_h(prefix + msg), "little") % _q
    R = _compress(_mul(r, _G))
    k = int.from_bytes(_h(R + A + msg), "little") % _q
    return R + int.to_bytes((r + k * a) % _q, 32, "little")


def verify(pub, msg, sig):
    if len(pub) != 32 or len(sig) != 64:
        return False
    A, R = _decompress(pub), _decompress(sig[:32])
    if A is None or R is None:
        return False
    s = int.from_bytes(sig[32:], "little")
    if s >= _q:
        return False
    k = int.from_bytes(_h(sig[:32] + pub + msg), "little") % _q
    return _eq(_mul(s, _G), _add(R, _mul(k, A)))


# ── 버전 ──
def vtuple(v):
    return tuple(int(x) for x in str(v).split("."))


def local_version(kit):
    try:
        return json.loads((Path(kit) / VERSION_FILE).read_text(encoding="utf-8"))["version"]
    except Exception:
        return "0.0.0"


def just_updated(kit):
    """방금 업데이트됐으면 새 버전 문자열을 돌려주고 표시를 지운다 (위젯이 켜질 때 한 번)."""
    f = Path(kit) / FLAG_FILE
    try:
        v = f.read_text(encoding="utf-8").strip()
        f.unlink()
        return v
    except Exception:
        return None


# ── 내려받기 ──
def _ssl_ready():
    try:                                   # 학교망 HTTPS 검사 — 윈도우 인증서 저장소를 쓴다 (키트와 같은 방법)
        import truststore
        truststore.inject_into_ssl()
    except Exception:
        pass


def _get(url, limit=50 * 1024 * 1024):
    req = urllib.request.Request(url, headers={"User-Agent": "work-widget-updater"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise RuntimeError("받은 파일이 너무 큽니다")
    return data


def check(kit):
    """새 버전이 있으면 서명이 확인된 manifest(dict), 없으면 None. 서명이 틀리면 예외."""
    if not PUBLIC_KEY_HEX or "WORK_WIDGET" in PUBLIC_KEY_HEX:
        return None                        # 공개 열쇠 없이 만든 묶음 — 업데이트를 쓰지 않는다
    _ssl_ready()
    raw = _get(BASE_URL + "manifest.json", 1024 * 1024)
    sig = _get(BASE_URL + "manifest.sig", 1024)
    if not verify(bytes.fromhex(PUBLIC_KEY_HEX), raw, bytes.fromhex(sig.decode("ascii").strip())):
        raise RuntimeError("새 버전의 서명이 맞지 않아 받지 않았습니다")
    m = json.loads(raw.decode("utf-8"))
    if m.get("format") != 1 or m.get("repo") != REPO:
        raise RuntimeError("새 버전 정보 형식이 맞지 않습니다")
    return m if vtuple(m["version"]) > vtuple(local_version(kit)) else None


_SKIP_DIRS = (".venv", "__pycache__")
_MAY_BE_LOCKED = (".ttf", ".otf")        # 위젯이 켜져 있는 동안 윈도우가 붙들고 있는 파일 (글꼴) — 못 덮어써도 업데이트는 계속한다


def _same(a, b):
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()
    except OSError:
        return False


def _copy_tree(src, dst):
    """src 의 파일을 dst 로 덮어쓴다 — 내용이 같은 파일은 건드리지 않고, 붙들린 글꼴은 건너뛴다.
    (예전엔 robocopy 를 썼는데, 위젯이 붙들고 있는 글꼴 파일에서 «다시 시도» 를 사실상 끝없이 되풀이해 «업데이트 중» 이 안 끝났다)"""
    src, dst = Path(src), Path(dst)
    for f in sorted(src.rglob("*")):
        rel = f.relative_to(src)
        if not f.is_file() or any(part in _SKIP_DIRS or part.startswith("chrome_profile") for part in rel.parts):
            continue
        t = dst / rel
        if t.exists() and _same(f, t):
            continue
        t.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                shutil.copyfile(f, t)
                break
            except OSError as e:
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                if t.suffix.lower() in _MAY_BE_LOCKED:
                    break
                raise RuntimeError("파일 복사 실패 (%s: %s)" % (rel.as_posix(), type(e).__name__))


def _robocopy(src, dst, extra=()):
    _copy_tree(src, dst)


def apply(kit, m, log=lambda s: None):
    """manifest m 의 app.zip 을 받아 확인하고 kit 에 덮어쓴다. 실패하면 되돌리고 예외."""
    kit = Path(kit)
    _ssl_ready()
    log("새 버전 받는 중")
    data = _get(BASE_URL + m["file"])
    if hashlib.sha256(data).hexdigest() != m["sha256"]:
        raise RuntimeError("받은 파일이 서명된 정보와 달라 설치하지 않았습니다")
    work = Path(tempfile.mkdtemp(prefix="work-widget-upd-"))
    try:
        zp = work / "app.zip"
        zp.write_bytes(data)
        new = work / "app"
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                if n.startswith(("/", "\\")) or ".." in Path(n).parts:
                    raise RuntimeError("묶음 안 파일 경로가 이상합니다")
            z.extractall(new)
        if local_version(new) != m["version"] or not (new / "widget" / "install.ps1").exists():
            raise RuntimeError("묶음 내용이 버전 정보와 맞지 않습니다")
        old_req = (kit / "requirements.txt").read_bytes() if (kit / "requirements.txt").exists() else b""
        backup = kit.parent / (kit.name + "-update-backup")
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        log("지금 버전 백업 중")
        _robocopy(kit, backup)
        try:
            log("새 파일로 바꾸는 중")
            _robocopy(new, kit)
            if (kit / "requirements.txt").read_bytes() != old_req:
                log("필요한 패키지 설치 중")
                py = kit / ".venv" / "Scripts" / "python.exe"
                r = subprocess.run([str(py), "-m", "pip", "install", "-r", str(kit / "requirements.txt"), "--quiet"],
                                   cwd=str(kit), capture_output=True, creationflags=NO_WINDOW, timeout=1800)
                if r.returncode != 0:
                    raise RuntimeError("패키지 설치 실패")
        except Exception:
            _robocopy(backup, kit)
            raise
        (kit / FLAG_FILE).write_text(m["version"], encoding="utf-8")
        return m["version"]
    finally:
        shutil.rmtree(work, ignore_errors=True)
