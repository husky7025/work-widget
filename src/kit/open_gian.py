# -*- coding: utf-8 -*-
"""K-에듀파인 > 문서관리 > 기안 > 공용서식 > «표준서식(결재4인,협조4인)» 으로 빈 내부기안 창을 연다.

위젯의 업무포털 크롬(포트 9324)을 그대로 이어 쓴다 — 새 크롬·새 로그인을 따로 만들지 않고, 끝나도 크롬을 닫지 않는다
(2026-11-16: 별도 크롬으로 두 번째 로그인을 하고 끝에 닫았더니 열려 있던 창들이 같이 닫혔다).
열기만 한다: 제목·본문을 채우거나 저장·상신하지 않는다. 로그인은 키트의 E.login (인증서 암호는 keyring, 이 파일은 다루지 않는다).
서식 이름을 못 찾으면 목록에 보이는 «결재4인» 서식 이름을 찍고 멈춘다 (아무것도 누르지 않음).
"""
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

import edufine_common as E
import edufine_gian as G
from edufine_gian import Stop

FORM_RE = re.compile(r"표준\s*서식\s*\(\s*결재\s*4인\s*,\s*협조\s*4인\s*\)")
WINDOW_TITLE_PART = "결재4인"        # 기안 창 제목에 들어 있는 글자
SITE = "edufine"


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def draft_windows():
    return G.windows("#32770", WINDOW_TITLE_PART, G.wxs_pids())


def allow_wxsclient(profile):
    """기안기(wxsclient://) «항상 열기» 를 위젯 크롬 프로필에 미리 넣는다 — 크롬이 «꺼져 있을 때만» (켜져 있으면 크롬이 덮어쓴다).
    없으면 «WXSClient 를 여시겠습니까?» 물음이 떠서 기안 창이 안 뜬다 (E.allow_wxsclient 와 같은 값, 프로필만 다르다)."""
    u = urlsplit(E.KLEF)
    origin = "%s://%s" % (u.scheme, u.netloc)
    pref = Path(profile) / "Default" / "Preferences"
    try:
        d = json.loads(pref.read_text(encoding="utf-8")) if pref.exists() else {}
        pairs = d.setdefault("protocol_handler", {}).setdefault("allowed_origin_protocol_pairs", {})
        if pairs.get(origin, {}).get("wxsclient") is True:
            return
        pairs.setdefault(origin, {})["wxsclient"] = True
        pref.parent.mkdir(parents=True, exist_ok=True)
        pref.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    from playwright.sync_api import sync_playwright
    if draft_windows():
        print("ℹ️  기안 창이 이미 열려 있습니다. 그 창을 쓰세요.", flush=True)
        return 0
    W = load_engine()
    port, profile = W.SITES[SITE]["port"], W.SITES[SITE]["profile"]
    if not W.alive(port):
        allow_wxsclient(profile)
    print("🔐  에듀파인 로그인 확인 중…", flush=True)
    W.ensure_chrome(SITE, minimized=False)
    with sync_playwright() as p:
        browser = W.connect_sync(p, port)
        ctx = browser.contexts[0]
        page = W.pick_page(ctx, SITE) or ctx.new_page()
        page.set_default_timeout(30_000)
        page.on("dialog", E.on_dialog)
        E.grant_local_network(ctx)
        _, urls = W.edufine_urls()
        if not W.edufine_session_ok(page, urls):
            W.edufine_login(E, ctx, page, urls)        # 업무포털 → 인증서 → 에듀파인 (이미 로그인돼 있으면 건너뜀)
        print("📂  문서관리 → 기안 → 공용서식", flush=True)
        page.goto(E.KLEF, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        for _ in range(3):
            E.close_modals(page)
            page.wait_for_timeout(800)
        page.locator('div[id$="btnMenu_A00AAB01:icontext"]').first.click()        # 상단 «문서관리»
        page.wait_for_timeout(1500)
        cell = page.locator('div[id$="grdMega_A00AAB0101.body.gridrow_0.cell_0_0"]').first
        b = None
        for _ in range(20):                                                       # 메가메뉴가 늦게 떠도 최대 10초 기다린다
            b = cell.bounding_box()
            if b:
                break
            page.wait_for_timeout(500)
        if not b:
            raise Stop("«문서관리» 메뉴가 10초 안에 안 열렸습니다")
        page.mouse.click(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        f = None
        for _ in range(30):
            f = next((x for x in page.frames if "retrieveCmmnFormatList" in x.url), None)
            if f:
                break
            page.wait_for_timeout(500)
        if not f:
            raise Stop("공용서식 목록이 15초 안에 안 떴습니다")
        item = f.get_by_text(FORM_RE)
        if item.count() == 0:
            names = [t.strip() for t in f.locator("text=결재4인").all_inner_texts()][:8]
            print("❌  «표준서식(결재4인,협조4인)» 을 목록에서 못 찾았습니다. 목록에 보이는 비슷한 서식: " + (" / ".join(names) or "(없음)"), flush=True)
            return 1
        item.first.click()                                                       # 한 번만 — 두 번이면 창이 두 개
        print("   서식을 눌렀습니다 — 기안 창을 기다립니다", flush=True)
        for _ in range(60):
            page.wait_for_timeout(500)
            if draft_windows():
                break
        else:
            raise Stop("기안 창이 30초 안에 안 떴습니다 (에듀파인 통합설치가 돼 있는지 보세요)")
    # 크롬은 닫지 않는다 (연결만 끊긴다)
    print("✅  내부기안 창을 열었습니다 (표준서식 결재4인·협조4인)", flush=True)
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
