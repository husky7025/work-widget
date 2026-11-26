# -*- coding: utf-8 -*-
"""K-에듀파인 > 학교회계 > 사업관리 > 사업담당 > 품의/정산 > «품의등록» 빈 화면을 새 탭으로 연다.

위젯의 업무포털 크롬(포트 9324)을 그대로 이어 쓴다 — 새 크롬을 만들지 않고, 끝나도 닫지 않는다 (업무포털 메인 탭은 건드리지 않는다).
열기만 한다: 제목·개요를 채우거나 저장·결재요청을 누르지 않는다. 로그인은 키트의 E.login (인증서 암호는 keyring, 이 파일은 다루지 않는다).
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

import edufine_common as E

SITE = "edufine"
TREE_TEXT = 'div[id*="divLnb.form.gridMenu.body.gridrow_"][id$="treeitemtext:text"]'


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree_item(page, name):
    loc = page.locator(TREE_TEXT).filter(has_text=re.compile("^%s$" % re.escape(name)))
    for i in range(loc.count()):
        if loc.nth(i).is_visible():
            return loc.nth(i)
    return None


def open_tree(page, name, child):
    """왼쪽 메뉴에서 name 을 눌러 child 가 보이게 한다 (이미 보이면 누르지 않는다)."""
    for _ in range(3):
        if tree_item(page, child):
            return
        item = tree_item(page, name)
        if not item:
            raise RuntimeError("왼쪽 메뉴에 «%s» 가 없습니다" % name)
        item.click()
        page.wait_for_timeout(1200)
    if not tree_item(page, child):
        raise RuntimeError("«%s» 아래에 «%s» 가 안 보입니다" % (name, child))


TOP_MENU = 'div[id*="TopFrame.form.divTopMenu.form.btnMenu_"][id$=":icontext"]'


def top_menus(page):
    try:
        return [t.strip() for t in page.locator(TOP_MENU).all_inner_texts()]
    except Exception:
        return []


def in_school_accounting(page):
    return "사업관리" in top_menus(page)           # 업무관리 쪽 위 메뉴는 문서관리·메모관리…, 학교회계 쪽은 사업관리·계약관리


DOWN_TRIES = (2, 1, 3, 4, 5)        # ↓ 를 몇 번 누를지 — 처음은 늘 쓰던 2번, 안 맞으면 차례로 다른 칸


def select_school_accounting(page):
    """왼쪽 위 «업무관리» 바(콤보)에서 «학교회계» 를 고른다. 목록 항목은 화면 밖에 그려져 마우스로 못 누르므로 키보드(↓↓ Enter)로 고른다.
    화면 크기와 상관없이 콤보의 실제 자리를 읽어 누르고, 공지 창이 늦게 떠서 누름이 먹히는 경우를 위해 몇 번 다시 시도한다."""
    for attempt in range(len(DOWN_TRIES) + 1):
        if in_school_accounting(page):
            return
        E.close_modals(page)
        page.wait_for_timeout(600)
        box = page.locator('div[id$="TopFrame.form.cboJobList"]').first.bounding_box()
        if not box:
            page.wait_for_timeout(1500)
            continue
        page.mouse.click(box["x"] + box["width"] - 15, box["y"] + box["height"] / 2)     # 오른쪽 ▼ 단추
        page.wait_for_timeout(1000)
        for _ in range(8):
            page.keyboard.press("ArrowUp")                                              # 맨 위로 맞춘 뒤
        for _ in range(DOWN_TRIES[attempt % len(DOWN_TRIES)]):
            page.keyboard.press("ArrowDown")                                            # 보통 업무관리 → … → 학교회계 (3번째) — 권한에 따라 순서가 다르면 다음 시도에 다른 칸을 고른다
        page.keyboard.press("Enter")
        for _ in range(10):
            page.wait_for_timeout(600)
            if in_school_accounting(page):
                return
    raise RuntimeError("«학교회계» 로 바꾸지 못했습니다 (왼쪽 위 «업무관리» 바를 직접 눌러 학교회계를 골라 보세요)")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    from playwright.sync_api import sync_playwright
    W = load_engine()
    port = W.SITES[SITE]["port"]
    print("🔐  에듀파인 로그인 확인 중…", flush=True)
    W.ensure_chrome(SITE, minimized=False)
    with sync_playwright() as p:
        browser = W.connect_sync(p, port)
        ctx = browser.contexts[0]
        page = ctx.new_page()                      # 업무포털 메인 탭은 그대로 둔다
        page.set_default_timeout(30_000)
        page.on("dialog", E.on_dialog)
        E.grant_local_network(ctx)
        _, urls = W.edufine_urls()
        if not W.edufine_session_ok(page, urls):
            W.edufine_login(E, ctx, page, urls)
        print("📂  학교회계 → 사업담당 → 품의/정산 → 품의등록", flush=True)
        W.goto(page, E.KLEF, wait_until="domcontentloaded")   # 로그인 직후 이동과 겹치면 다시 시도
        page.wait_for_timeout(5000)
        for _ in range(3):
            E.close_modals(page)
            page.wait_for_timeout(800)
        select_school_accounting(page)
        open_tree(page, "사업담당", "품의/정산")
        open_tree(page, "품의/정산", "품의등록")
        tree_item(page, "품의등록").click()
        for _ in range(30):
            page.wait_for_timeout(500)
            if page.locator("div").filter(has_text=re.compile("^품의번호$")).count():
                break
        else:
            raise RuntimeError("품의등록 화면이 15초 안에 안 떴습니다")
    # 크롬·탭은 닫지 않는다 (연결만 끊긴다)
    print("✅  품의등록 화면을 열었습니다", flush=True)
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
