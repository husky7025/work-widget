# -*- coding: utf-8 -*-
"""업무포털 로그인 → 교육행정데이터통합관리 «데이터취합 > 제출자료 > 기관접수대기» 탭까지만 연다. 접수·제출은 안 한다.

업무포털 메인의 «데이터취합» 링크와 같은 주소(taskPotl?edmgrUrl=...)로 들어간다. agrtChcGbn=1 이 «기관접수대기» 탭이다
(2=내담당, 2026-11-17 대전 실측). 로그인은 open_portal.py 와 같이 키트의 edufine_common.login 이 한다.
마지막에 «JEOPSU N» 한 줄을 찍어 위젯이 건수 칸을 바로 고칠 수 있게 한다.
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

SCREEN = "in/dam/apm/wm/in_dam_apmwm01_m01&agrtChcGbn=1"
COUNT_JS = r"""() => { const m = (document.body && document.body.innerText || '').match(/기관접수대기\s*\(?\s*(\d+)/); return m ? m[1] : null }"""


def stable_count(page, tries=40):
    """화면이 뜰 때 잠깐 «기관접수대기 0» 이 보였다가 진짜 숫자로 바뀐다 → 같은 숫자가 세 번 연달아 나와야 믿는다 (최대 약 20초)."""
    last, same = None, 0
    for _ in range(tries):
        page.wait_for_timeout(500)
        try:
            v = page.evaluate(COUNT_JS)
        except Exception:
            v = None
        if v is not None and v == last:
            same += 1
            if same >= 2:
                return v
        else:
            same = 0
        last = v
    return None


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def edmgr_base(portal_url):
    """https://dje.eduptl.kr/... → https://dje.edmgr.kr (지역 앞부분은 업무포털 주소를 따른다)"""
    m = re.match(r"https://([a-z]+)\.eduptl\.kr", portal_url or "")
    if not m:
        raise RuntimeError("업무포털 주소에서 지역을 알아내지 못했습니다")
    return "https://%s.edmgr.kr" % m.group(1)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    from playwright.sync_api import sync_playwright
    W = load_engine()
    import edufine_common as E
    site = "edufine"
    print("🔐  업무포털 로그인 중…", flush=True)
    W.ensure_chrome(site, minimized=False)
    with sync_playwright() as p:
        browser = W.connect_sync(p, W.SITES[site]["port"])
        ctx = browser.contexts[0]
        blank = ("about:blank", "chrome://newtab/", "chrome://new-tab-page/", "edge://newtab/")
        portal = next((pg for pg in ctx.pages if "bpm_man_mn00_001" in pg.url), None)
        if portal is None:                              # 로그인이 안 돼 있으면 open_portal 과 같은 방법으로 로그인
            portal = (next((pg for pg in ctx.pages if any(k in pg.url for k in W.SITES[site]["match"])), None)
                      or next((pg for pg in ctx.pages if pg.url in blank), None)
                      or ctx.new_page())
            portal.set_default_timeout(30_000)
            portal.on("dialog", E.on_dialog)
            E.grant_local_network(ctx)
            cfg, pw = W.cfg_and_pw()
            E.login(portal, cfg["cert_name"], pw)
            if "bpm_man_mn00_001" not in portal.url:
                print("❌  업무포털 로그인이 끝나지 않았습니다. 크롬 창을 확인하세요.", flush=True)
                return 1
        base = edmgr_base(portal.url)
        print("📂  교육행정데이터통합관리 기관접수대기 화면을 여는 중…", flush=True)
        page = next((pg for pg in ctx.pages if "edmgr.kr" in pg.url), None) or ctx.new_page()
        page.set_default_timeout(30_000)
        page.on("dialog", E.on_dialog)
        page.goto("%s/taskPotl?edmgrUrl=%s" % (base, SCREEN), wait_until="domcontentloaded")
        n = stable_count(page)
        W.to_front_sync(page)
        if n is None:
            print("❌  기관접수대기 화면이 뜨지 않았습니다 (로그인이 풀렸거나 화면이 바뀌었을 수 있습니다). 크롬 창을 확인하세요.", flush=True)
            return 1
        print("✅  기관접수대기 화면을 열었습니다 (%s건)" % n, flush=True)
        print("JEOPSU %s" % n, flush=True)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("❌  " + msg, flush=True)
        sys.exit(1)
