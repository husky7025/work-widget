# -*- coding: utf-8 -*-
"""업무포털 메인의 «K-에듀파인 전자결재 현황 > 결재(긴급)» 링크를 눌러 에듀파인 «결재대기함» 을 연다. 열기만 한다.

사람이 업무포털에서 그 숫자를 눌러 들어가는 것과 같다 (링크는 target=_blank → 새 탭). 문서를 열거나 결재·반려·상신은 누르지 않는다.
이미 결재대기함 탭이 열려 있으면 새로 열지 않고 그 탭을 앞으로 꺼낸다. 로그인이 안 돼 있으면 open_jeopsu.py 와 같은 방법으로 로그인한다.
"""
import importlib.util
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

LINK = '#keduBox a[href*="link=sanctnWait"]'
BLANK = ("about:blank", "chrome://newtab/", "chrome://new-tab-page/", "edge://newtab/")


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SCREEN_JS = r"""() => { const t = (document.body && document.body.innerText) || ''; return /RESERVED\.\s*\n결재대기\s*\n\(/.test(t) }"""


def is_sanctn_tab(pg):
    """에듀파인 탭 중 지금 화면 제목이 «결재대기» 인 탭 (주소는 늘 같아서 화면 글자로 알아본다). 다른 화면을 보고 있는 탭은 건드리지 않는다."""
    try:
        return "keris_ui" in pg.url and bool(pg.evaluate(SCREEN_JS))
    except Exception:
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    from playwright.sync_api import sync_playwright
    W = load_engine()
    import edufine_common as E
    site = "edufine"
    print("🔐  업무포털 로그인 확인 중…", flush=True)
    W.ensure_chrome(site, minimized=False)
    with sync_playwright() as p:
        browser = W.connect_sync(p, W.SITES[site]["port"])
        ctx = browser.contexts[0]
        portal = None
        for _ in range(8):                              # 건수 자동 조회가 포털을 새로고침하는 순간이면 잠깐 주소가 바뀌어 있다 → 4초까지 기다려 본다
            portal = next((pg for pg in ctx.pages if "bpm_man_mn00_001" in pg.url), None)
            if portal is not None:
                break
            time.sleep(0.5)
        if portal is None:                              # 정말 로그인이 안 돼 있으면 open_portal 과 같은 방법으로 로그인
            # 업무포털·로그인 화면 탭이나 빈 탭만 쓴다 — 에듀파인 등 다른 탭을 로그인 화면으로 바꿔 버리지 않게
            portal = (next((pg for pg in ctx.pages if "eduptl.kr" in pg.url or "idp" in pg.url), None)
                      or next((pg for pg in ctx.pages if pg.url in BLANK), None)
                      or ctx.new_page())
            portal.set_default_timeout(30_000)
            portal.on("dialog", E.on_dialog)
            E.grant_local_network(ctx)
            cfg, pw = W.cfg_and_pw()
            E.login(portal, cfg["cert_name"], pw)
            if "bpm_man_mn00_001" not in portal.url:
                print("❌  업무포털 로그인이 끝나지 않았습니다. 크롬 창을 확인하세요.", flush=True)
                return 1
        old = next((pg for pg in ctx.pages if is_sanctn_tab(pg)), None)
        if old is not None:
            W.to_front_sync(old)
            print("✅  결재대기함을 열었습니다 (이미 열려 있던 탭 — 최신으로 보려면 [조회])", flush=True)
            return 0
        print("📂  결재대기함을 여는 중…", flush=True)
        portal.set_default_timeout(20_000)
        link = portal.locator(LINK).first
        try:
            link.wait_for(state="visible", timeout=20_000)
        except Exception:
            print("❌  업무포털에서 결재대기 링크를 찾지 못했습니다 (에듀파인 연결이 안 됐을 수 있습니다)", flush=True)
            return 1
        with ctx.expect_page(timeout=30_000) as info:
            link.click()
        page = info.value
        page.on("dialog", E.on_dialog)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=30_000)
        except Exception:
            pass
        W.to_front_sync(page)
        print("✅  결재대기함을 열었습니다", flush=True)
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
