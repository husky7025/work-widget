"""업무위젯 설치 묶음 만들기·올리기 — build.cmd 로 실행한다 (키트 파이썬: 서명 열쇠를 자격 증명 관리자에서 읽으려고)

  build.cmd                    묶음만 만든다 (../업무위젯_설치묶음.zip)
  build.cmd --publish          VERSION 의 버전으로 묶음을 만들어 서명하고 GitHub 릴리스로 올린다
                               → 선생님들 위젯이 하루 안에 알아서 새 버전으로 바뀐다
  build.cmd --keygen           서명 열쇠를 처음 한 번 만든다 (비밀 열쇠는 이 PC의 Windows 자격 증명 관리자에만)
  build.cmd --export-key 폴더  비밀 열쇠를 USB 등에 백업한다 (잃어버리면 다시는 업데이트를 올릴 수 없다)
  build.cmd --import-key 파일  백업해 둔 비밀 열쇠를 새 PC에 넣는다

1) 나이스 자동화 키트(MIT)를 KIT_SHA 커밋으로 고정해 받는다 (%TEMP%\\work-widget-build\\cache 에 보관)
2) src/ 의 업무 위젯 파일을 얹고, 설정 창 문구 등을 바꾼다 → payload/app.zip
3) 겉 묶음에는 영문 이름 파일만 넣는다 (일부 윈도우의 «모두 풀기»가 zip 안 한글 이름을 깨뜨려 설치가 멈추는 것을 막는다.
   한글 이름 파일은 app.zip 안에 두고, 설치기가 PowerShell Expand-Archive 로 UTF-8 이름 그대로 푼다)

키트 버전을 올리려면 KIT_SHA 만 바꾸고 다시 실행한 뒤, 깨끗한 PC에서 설치를 시험한다.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

KIT_REPO = "workcalmkite-hue/neis-automation-kit"
KIT_SHA = "4815f63c672e0ce424e6c5af1b5df926a77164d6"   # 2026-11-12 main — 이 버전으로 시험함

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
SCRIPTS = HERE / "scripts"
BUILD = Path(tempfile.gettempdir()) / "work-widget-build"   # OneDrive 폴더 밖 (동기화가 파일을 잡고 있어 지우기 실패)
OUT_ZIP = HERE.parent / "업무위젯_설치묶음.zip"
VERSION = (HERE / "VERSION").read_text(encoding="utf-8").strip()
PUBKEY_FILE = HERE / "signing_public_key.txt"
REPO = "husky7025/work-widget"
KEYRING_SERVICE, KEYRING_USER = "work-widget-signing", "ed25519-seed"
sys.path.insert(0, str(SRC / "kit"))
import work_widget_update as U  # noqa: E402  (서명·검증 코드를 위젯과 같이 쓴다)

# 설정 창 맨 위 안내 문구 — 보안에 민감한 선생님을 위해 «서버로 보내지 않음»을 분명히 적는다
PW_OLD = '''    tk.Label(root, text="인증서 암호는 이 컴퓨터의 «Windows 자격 증명 관리자»에만 저장되고, 파일에는 남지 않아요.",
             font=("맑은 고딕", 9), fg=SUB, bg="white").grid(row=1, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 10))'''
PW_NEW = '''    tk.Label(root, text="🔒 인증서 암호는 선생님 PC에만 저장되고, 위젯 만든 사람이나 다른 서버로 보내지 않아요.\\n"
                        "     (이 PC의 «Windows 자격 증명 관리자»에 보관 · 로그인할 때 인증서 창에 대신 입력하는 데만 써요)",
             font=("맑은 고딕", 9, "bold"), fg="#166534", bg="#dcfce7", justify="left", anchor="w", padx=10, pady=6).grid(
        row=1, column=0, columnspan=2, sticky="we", padx=18, pady=(0, 10))'''

PATCHES = {
    # 출근·퇴근 기본값 08:00 / 16:00 (처음 설치할 때 칸에 미리 채워지는 값 — 선생님이 바꿀 수는 있다)
    "widget/바로가기_설정창.pyw": [
        (PW_OLD, PW_NEW),
        ('old.get("work_start", "08:40")', 'old.get("work_start", "08:00")'),
        ('old.get("work_end", "16:20")', 'old.get("work_end", "16:00")'),
        ('08:40 처럼 적어 주세요', '08:00 처럼 적어 주세요'),
    ],
    # 키트 설정 창이 바로가기를 만들 때도 «업무위젯» 이름·새 아이콘을 쓰게 한다
    "widget/바로가기_설정.py": [
        ('"나이스 에듀파인 바로가기.lnk"', '"업무위젯.lnk"'),
        ('% (lnk, pyw, target, HERE, pyw))', '% (lnk, pyw, target, HERE, HERE / "업무위젯.ico"))'),
        ('old.get("work_start", "08:40")', 'old.get("work_start", "08:00")'),
        ('old.get("work_end", "16:20")', 'old.get("work_end", "16:00")'),
    ],
    # 설정에 시각이 비어 있을 때 위젯 [복무] 창이 쓰는 값
    "widget/바로가기위젯_원본.pyw": [
        ('c.get("work_end") or "16:20"', 'c.get("work_end") or "16:00"'),
        ('% (end_default, c.get("work_start") or "08:40")', '% (end_default, c.get("work_start") or "08:00")'),
        ('v_start.set(c.get("work_start") or "08:40")', 'v_start.set(c.get("work_start") or "08:00")'),
    ],
    # 위젯용 크롬을 평소 크롬과 한눈에 구별되게 — 초록색 테마 + 작업표시줄 창 이름 «업무용 크롬 (위젯)»
    # (평소 크롬은 원격 조종을 막으므로 위젯은 따로 된 크롬을 쓴다. 색은 선생님이 직접 바꾼 적이 없을 때만 넣는다)
    "widget/바로가기_엔진.py": [
        ('''        d.setdefault("browser", {}).setdefault("window_placement", {})["maximized"] = False
''', '''        d.setdefault("browser", {}).setdefault("window_placement", {})["maximized"] = False
        th = d["browser"].setdefault("theme", {})
        if "user_color2" not in th and not th.get("id"):
            th.update({"user_color2": -15293622, "color_variant2": 3, "color_scheme2": 1})   # #16A34A 초록
        if d["profile"].get("name") in (None, "", "내 Chrome", "Person 1", "사용자 1"):
            d["profile"]["name"] = "업무용 (위젯)"
'''),
        ('''    "--test-type", "--noerrdialogs", "--no-first-run", "--no-default-browser-check",
''', '''    "--test-type", "--noerrdialogs", "--no-first-run", "--no-default-browser-check",
    "--window-name=업무용 크롬 (위젯)",
'''),
    ],
}


def fetch_kit() -> Path:
    cache = BUILD / "cache" / f"kit-{KIT_SHA[:12]}.zip"
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/{KIT_REPO}/archive/{KIT_SHA}.zip"
        print("키트 받는 중:", url)
        with urllib.request.urlopen(url, timeout=60) as r:
            cache.write_bytes(r.read())
    return cache


def main():
    stage = BUILD / "app"
    dist = BUILD / "dist"
    for d in (stage, dist):
        if d.exists():
            shutil.rmtree(d)
    stage.mkdir(parents=True)

    # 1) 고정 버전 키트 풀기 (맨 위 «저장소-sha/» 폴더는 벗긴다)
    with zipfile.ZipFile(fetch_kit()) as z:
        for info in z.infolist():
            rel = info.filename.split("/", 1)[1] if "/" in info.filename else ""
            if not rel or info.is_dir():
                continue
            dst = stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(z.read(info))

    # 2) 원본 위젯 보관 → 업무 위젯 얹기
    wdir = stage / "widget"
    shutil.copy2(wdir / "바로가기위젯.pyw", wdir / "바로가기위젯_원본.pyw")
    for f in (SRC / "widget").iterdir():
        if f.is_file():
            shutil.copy2(f, wdir / f.name)
    for f in (SRC / "kit").iterdir():
        if f.is_file() and f.suffix in (".py", ".pyw"):
            shutil.copy2(f, stage / f.name)

    # 3) 문구·이름 바꾸기 — 키트가 바뀌어 못 찾으면 묶음을 만들지 않고 멈춘다
    for rel, pairs in PATCHES.items():
        p = stage / rel
        s = p.read_text(encoding="utf-8")
        for old, new in pairs:
            if s.count(old) != 1:
                sys.exit(f"X {rel} 에서 바꿀 곳을 찾지 못했습니다: {old[:60]!r}")
            s = s.replace(old, new)
        p.write_text(s, encoding="utf-8")

    # 3-1) 버전 표시 + 업데이트 확인용 공개 열쇠
    (stage / U.VERSION_FILE).write_text(json.dumps({"version": VERSION, "kit": KIT_SHA[:12]}), encoding="utf-8")
    pub = PUBKEY_FILE.read_text(encoding="ascii").strip() if PUBKEY_FILE.exists() else ""
    up = stage / "work_widget_update.py"
    if pub:
        t = up.read_text(encoding="utf-8")
        if t.count('"__WORK_WIDGET_PUBKEY__"') != 1:
            sys.exit("X work_widget_update.py 에서 공개 열쇠 자리를 찾지 못했습니다")
        up.write_text(t.replace('"__WORK_WIDGET_PUBKEY__"', '"%s"' % pub), encoding="utf-8")
    else:
        print("! 서명 공개 열쇠가 없어 자동 업데이트가 꺼진 묶음입니다 (build.cmd --keygen)")

    # 4) payload/app.zip
    payload = dist / "payload"
    payload.mkdir(parents=True)
    with zipfile.ZipFile(payload / "app.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(stage.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(stage).as_posix())
    for name in ("install_gui.ps1", "install_widget.ps1", "uninstall_widget.ps1"):
        shutil.copy2(SCRIPTS / name, payload / name)
    shutil.copy2(SCRIPTS / "install_widget.cmd", dist / "install_widget.cmd")
    shutil.copy2(SCRIPTS / "uninstall_widget.cmd", dist / "uninstall_widget.cmd")
    shutil.copy2(HERE / "안내서.html", dist / "guide.html")

    # 5) 겉 묶음 — 영문 이름만 들어갔는지 확인
    names = [f.relative_to(dist).as_posix() for f in sorted(dist.rglob("*")) if f.is_file()]
    bad = [n for n in names if not n.isascii()]
    if bad:
        sys.exit(f"X 겉 묶음에 한글 이름이 있습니다: {bad}")
    tmp = OUT_ZIP.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n in names:
            z.write(dist / n, n)
    tmp.replace(OUT_ZIP)
    print(f"OK {OUT_ZIP.name} v{VERSION} ({OUT_ZIP.stat().st_size // 1024} KB) — 키트 {KIT_SHA[:7]}")
    for n in names:
        print("  ", n)
    return payload / "app.zip"


# ── 서명 열쇠 (비밀 열쇠는 Windows 자격 증명 관리자에만 — Git·채팅·로그에 남기지 않는다) ──
def _keyring():
    try:
        import keyring
        return keyring
    except ImportError:
        sys.exit("X keyring 이 없는 파이썬입니다 — build.cmd 로 실행하세요")


def _pub_hex():
    return PUBKEY_FILE.read_text(encoding="ascii").strip()


def load_seed():
    v = _keyring().get_password(KEYRING_SERVICE, KEYRING_USER)
    if not v:
        sys.exit("X 이 PC에 서명 열쇠가 없습니다 (처음이면 build.cmd --keygen, 다른 PC면 --import-key)")
    seed = bytes.fromhex(v)
    if PUBKEY_FILE.exists() and U.public_key(seed).hex() != _pub_hex():
        sys.exit("X 저장된 비밀 열쇠가 signing_public_key.txt 와 짝이 아닙니다")
    return seed


def keygen():
    kr = _keyring()
    if kr.get_password(KEYRING_SERVICE, KEYRING_USER) or PUBKEY_FILE.exists():
        sys.exit("X 이미 서명 열쇠가 있습니다. 새로 만들면 이미 깔린 위젯들이 업데이트를 못 받습니다")
    seed = os.urandom(32)
    kr.set_password(KEYRING_SERVICE, KEYRING_USER, seed.hex())
    PUBKEY_FILE.write_text(U.public_key(seed).hex() + "\n", encoding="ascii")
    print("OK 서명 열쇠를 만들었습니다. 비밀 열쇠: Windows 자격 증명 관리자 «%s»" % KEYRING_SERVICE)
    print("   공개 열쇠: %s" % PUBKEY_FILE.name)
    print("   꼭 백업하세요: build.cmd --export-key <USB 폴더>")


def export_key(folder):
    seed = load_seed()
    out = Path(folder) / "work-widget-signing-key.txt"
    out.write_text(seed.hex() + "\n", encoding="ascii")
    print("OK 비밀 열쇠를 %s 에 저장했습니다. 남에게 주거나 클라우드·Git에 올리지 마세요." % out)


def import_key(path):
    seed = bytes.fromhex(Path(path).read_text(encoding="ascii").strip())
    if PUBKEY_FILE.exists() and U.public_key(seed).hex() != _pub_hex():
        sys.exit("X 이 비밀 열쇠는 signing_public_key.txt 와 짝이 아닙니다")
    _keyring().set_password(KEYRING_SERVICE, KEYRING_USER, seed.hex())
    print("OK 비밀 열쇠를 이 PC의 자격 증명 관리자에 넣었습니다. 백업 파일은 안전한 곳에 두세요.")


# ── GitHub 릴리스로 올리기 ──
def _run(args):
    return subprocess.run(args, cwd=str(HERE), capture_output=True, text=True, encoding="utf-8", errors="replace")


def publish(notes):
    seed = load_seed()
    if not PUBKEY_FILE.exists():
        sys.exit("X signing_public_key.txt 가 없습니다")
    st = _run(["git", "status", "--porcelain"])
    if st.returncode != 0 or st.stdout.strip():
        sys.exit("X 커밋하지 않은 변경이 있습니다. 먼저 커밋·push 하세요:\n" + st.stdout[:800])
    ahead = _run(["git", "log", "@{u}..", "--oneline"])
    if ahead.returncode != 0 or ahead.stdout.strip():
        sys.exit("X push 하지 않은 커밋이 있습니다 (git push)")
    last = _run(["gh", "release", "view", "--repo", REPO, "--json", "tagName", "-q", ".tagName"])
    if last.returncode == 0 and last.stdout.strip():
        if U.vtuple(VERSION) <= U.vtuple(last.stdout.strip().lstrip("v")):
            sys.exit("X VERSION(%s) 을 지난 릴리스(%s)보다 올려 주세요" % (VERSION, last.stdout.strip()))
    app = main()
    data = app.read_bytes()
    manifest = json.dumps({"format": 1, "repo": REPO, "version": VERSION, "file": "app.zip",
                           "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                           "published": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                          ensure_ascii=False, indent=1).encode("utf-8")
    sig = U.sign(seed, manifest)
    if not U.verify(bytes.fromhex(_pub_hex()), manifest, sig):
        sys.exit("X 서명 자체 확인 실패")
    rel = BUILD / "release"
    if rel.exists():
        shutil.rmtree(rel)
    rel.mkdir(parents=True)
    shutil.copy2(app, rel / "app.zip")
    shutil.copy2(OUT_ZIP, rel / "work-widget-setup.zip")
    (rel / "manifest.json").write_bytes(manifest)
    (rel / "manifest.sig").write_text(sig.hex() + "\n", encoding="ascii")
    head = _run(["git", "rev-parse", "HEAD"]).stdout.strip()
    r = _run(["gh", "release", "create", "v" + VERSION, "--repo", REPO, "--target", head,
              "--title", "업무위젯 v" + VERSION, "--notes", notes or ("업무위젯 v" + VERSION),
              str(rel / "app.zip"), str(rel / "manifest.json"), str(rel / "manifest.sig"), str(rel / "work-widget-setup.zip")])
    if r.returncode != 0:
        sys.exit("X 릴리스를 만들지 못했습니다: " + (r.stderr or r.stdout)[:400])
    print("OK v%s 를 올렸습니다: %s" % (VERSION, r.stdout.strip()))
    print("   새 선생님용 설치 파일: https://github.com/%s/releases/latest/download/work-widget-setup.zip" % REPO)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--notes", default="")
    ap.add_argument("--keygen", action="store_true")
    ap.add_argument("--export-key")
    ap.add_argument("--import-key")
    a = ap.parse_args()
    if a.keygen:
        keygen()
    elif a.export_key:
        export_key(a.export_key)
    elif a.import_key:
        import_key(a.import_key)
    elif a.publish:
        publish(a.notes)
    else:
        main()
