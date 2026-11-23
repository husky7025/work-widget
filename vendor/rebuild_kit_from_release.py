# v0.10.1 설치 묶음의 payload/app.zip 에서 원본 키트(KIT_SHA) zip 을 되살린다
import sys, io, zipfile, json, hashlib
from pathlib import Path
DEPLOY = Path(sys.argv[1]); REL = Path(sys.argv[2]); OUT = Path(sys.argv[3])
sys.path.insert(0, str(DEPLOY))
import build as B
U = B.U
# 0) 릴리스 서명 확인 (진짜 우리 릴리스인지)
man = (REL / "manifest.json").read_bytes(); sig = bytes.fromhex((REL / "manifest.sig").read_text().strip())
assert U.verify(bytes.fromhex(B._pub_hex()), man, sig), "서명 불일치"
m = json.loads(man); upd = (REL / "app.zip").read_bytes()
assert hashlib.sha256(upd).hexdigest() == m["sha256"] and m["version"] == "0.10.1"
with zipfile.ZipFile(REL / "work-widget-setup.zip") as z:
    app = z.read("payload/app.zip")
files = {}
with zipfile.ZipFile(io.BytesIO(app)) as z:
    ver = json.loads(z.read(U.VERSION_FILE))
    assert ver["kit"] == B.KIT_SHA[:12], ver
    for i in z.infolist():
        if not i.is_dir(): files[i.filename] = z.read(i)
    # 업데이트 묶음과 같은 내용인지 (글꼴 빼고)
    with zipfile.ZipFile(io.BytesIO(upd)) as zu:
        for n in zu.namelist():
            assert zu.read(n) == files[n], n
def unpatch(s, old, new, rel):
    """new 가 여러 번 나오면, 되돌린 뒤 build.py 처럼 다시 패치했을 때 지금 글과 똑같아지는 자리만 고른다 (줄 머리 우선)."""
    pos, i = [], s.find(new)
    while i >= 0:
        pos.append(i); i = s.find(new, i + 1)
    ok = []
    for i in pos:
        t = s[:i] + old + s[i + len(new):]
        if t.count(old) == 1 and t.replace(old, new) == s:
            ok.append((i, t))
    if len(ok) > 1 and new[:1] in (" ", "\t"):
        ok = [(i, t) for i, t in ok if i == 0 or s[i - 1] == "\n"]
    assert len(ok) == 1, (rel, new[:60], len(pos), len(ok))
    return ok[0][1]


# 1) 패치 되돌리기 (new → old, 정확히 한 번씩)
for rel, pairs in B.PATCHES.items():
    s = files[rel].decode("utf-8").replace("\r\n", "\n")   # build.py 의 write_text 가 CRLF 로 썼다 (다시 읽을 땐 어차피 \n)
    for old, new in reversed(pairs):
        s = unpatch(s, old, new, rel)
    files[rel] = s.encode("utf-8")
# 2) 원래 위젯 = 패치 되돌린 _원본
files["widget/바로가기위젯.pyw"] = files.pop("widget/바로가기위젯_원본.pyw")
# 3) build.py 가 얹는 것 빼기 (다시 빌드하면 어차피 덮어쓴다)
drop = {U.VERSION_FILE, "widget/사용설명서.html"}
drop |= {"widget/" + f.name for f in (DEPLOY / "src/widget").iterdir() if f.is_file() and f.name != "바로가기위젯.pyw"}
drop |= {f.name for f in (DEPLOY / "src/kit").iterdir() if f.is_file() and f.suffix in (".py", ".pyw")}
for n in sorted(drop & files.keys()):
    print("  뺌:", n); del files[n]
top = "neis-automation-kit-%s/" % B.KIT_SHA
OUT.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for n in sorted(files): z.writestr(top + n, files[n])
print("OK", OUT, len(files), "files", OUT.stat().st_size // 1024, "KB")
