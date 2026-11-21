# -*- coding: utf-8 -*-
"""업무위젯 «펼침 메뉴» — 나이스·K-에듀파인의 하위 메뉴 화면 하나를 연다.

  python work_widget_menu.py open-neis '<경로 JSON>' 이름     예) '[["복무",0],["개인근무상황관리",1]]'
  python work_widget_menu.py open-edufine <메뉴ID> 이름       예) A00AAB0106001 (기안한문서)

사람이 메뉴를 누르는 것과 같다 — 나이스는 메뉴 글자를 차례로 누르고, 에듀파인은 사람이 메뉴를 누를 때 에듀파인이 부르는
gfnOpenMenu(메뉴ID) 를 그대로 부른다 (권한 없는 메뉴는 에듀파인 메뉴 표에 없으므로 열리지 않는다).
화면을 열기만 하고 신청·저장·결재·상신은 누르지 않는다.
로그인은 open_neis.py · 에듀파인 키트 로그인을 그대로 쓴다 (인증서 암호는 keyring, 이 파일은 다루지 않는다).
"""
import asyncio
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

SITE = "edufine"                       # 나이스·에듀파인 모두 위젯 크롬(포트 9324) 한 개를 쓴다

EDU_APP_JS = r"""() => { try { const a = nexacro.getApplication(); return !!(a && a.gdsMenu && a.gdsMenu.getRowCount() > 0); } catch (e) { return false; } }"""
EDU_OPEN_JS = r"""(id) => { const a = nexacro.getApplication(), fs = a.mainframe.MainVFrameSet.frames;
  let f = null; for (let i = 0; i < fs.length; i++) { const x = fs[i]; if (x && x.form && typeof x.form.gfnOpenMenu === 'function') { f = x.form; if (x.name === 'TopFrame') break; } }
  if (!f) return 'nofn';
  a.gdsMenu.filter('');
  if (a.gdsMenu.findRow('menuId', id) < 0) return 'nomenu';
  f.gfnOpenMenu(id); return 'ok'; }"""
EDU_ACTIVE_JS = r"""() => { try { return String(nexacro.getApplication().gv_openMenuId || ''); } catch (e) { return ''; } }"""


def say(msg):
    print(msg, flush=True)


def load_engine():
    spec = importlib.util.spec_from_file_location("wengine", HERE / "widget" / "바로가기_엔진.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 나이스 ────────────────────────────────────────────────
def neis_login():
    """open_neis.py 와 똑같이 — 로그인된 나이스 탭이 있으면 그대로, 없으면 인증서 로그인."""
    spec = importlib.util.spec_from_file_location("open_neis", HERE / "open_neis.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    asyncio.run(mod.run())


def neis_page(ctx):
    for pg in ctx.pages:
        if ".neis.go.kr" in pg.url and "/jsp/main" in pg.url:
            return pg
    return next((pg for pg in ctx.pages if ".neis.go.kr" in pg.url), None)


def neis_link(page, name, lv):
    """나이스 메뉴 링크는 «이름 N단계 메뉴항목» 처럼 단계가 글자에 붙어 있다 (화면 읽기 프로그램용 글자). 보이는 것만."""
    loc = page.locator("a").filter(has_text=re.compile(r"^\s*%s\s+%d단계" % (re.escape(name), lv)))
    for i in range(loc.count()):
        if loc.nth(i).is_visible():
            return loc.nth(i)
    return None


def neis_home(page):
    """나의메뉴(복무·급여…) 링크는 나이스 첫 화면에만 보인다 → 왼쪽 위 나이스 로고를 눌러 첫 화면으로."""
    logo = page.locator('[aria-label="나이스로고"]').first
    if logo.count():
        logo.click()
        page.wait_for_timeout(2500)


def neis_open(page, path):
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    for idx, (name, lv) in enumerate(path):
        link = None
        for _ in range(3):
            link = neis_link(page, name, lv)
            if link is not None:
                break
            if idx == 0:
                neis_home(page)
            else:                                   # 위 단계가 덜 펼쳐졌으면 한 번 더 누른다
                prev = neis_link(page, *path[idx - 1])
                if prev is not None:
                    prev.click()
                page.wait_for_timeout(1200)
        if link is None:
            raise RuntimeError("나이스 메뉴에서 «%s» 를 찾지 못했습니다" % name)
        link.click()
        page.wait_for_timeout(1300)


# ── K-에듀파인 ────────────────────────────────────────────
def edufine_page(ctx, W, E):
    """로그인된 에듀파인 탭 (이미 있으면 그 탭, 없으면 새 탭에서 로그인)."""
    page = next((pg for pg in ctx.pages if "klef." in pg.url and "keris_ui/main.do" in pg.url), None)
    if page is None:
        page = ctx.new_page()
        page.set_default_timeout(30_000)
        page.on("dialog", E.on_dialog)
        E.grant_local_network(ctx)
        _, urls = W.edufine_urls()
        if not W.edufine_session_ok(page, urls):
            W.edufine_login(E, ctx, page, urls)
        page.goto(E.KLEF, wait_until="domcontentloaded")
    for _ in range(60):
        try:
            if page.evaluate(EDU_APP_JS):
                break
        except Exception:
            pass
        page.wait_for_timeout(500)
    else:
        raise RuntimeError("에듀파인 화면이 30초 안에 준비되지 않았습니다")
    E.close_modals(page)
    return page


def edufine_open(page, E, W, menu_id):
    r = page.evaluate(EDU_OPEN_JS, menu_id)
    if r == "nomenu":
        raise RuntimeError("에듀파인에서 이 메뉴 권한이 없습니다")
    if r != "ok":
        raise RuntimeError("에듀파인 메뉴 열기 기능을 찾지 못했습니다")
    for _ in range(30):
        page.wait_for_timeout(500)
        if ("_%s_" % menu_id) in page.evaluate(EDU_ACTIVE_JS):
            break
    E.close_modals(page)
    W.to_front_sync(page)


# ── 명령 ─────────────────────────────────────────────────
def cmd_open_neis(path_json, label):
    path = [(str(n), int(lv)) for n, lv in json.loads(path_json)]
    from playwright.sync_api import sync_playwright
    W = load_engine()
    say("🔐  나이스 로그인 확인 중…")
    neis_login()
    with sync_playwright() as p:
        ctx = W.connect_sync(p, W.SITES[SITE]["port"]).contexts[0]
        page = neis_page(ctx)
        if page is None:
            raise RuntimeError("나이스 탭을 찾지 못했습니다")
        say("📂  %s 여는 중…" % label)
        neis_open(page, path)
        W.to_front_sync(page)
    say("✅  열었습니다: %s" % label)
    return 0


def cmd_open_edufine(menu_id, label):
    if not re.fullmatch(r"[A-Z0-9]{4,20}", menu_id):
        raise RuntimeError("메뉴 ID 가 이상합니다")
    from playwright.sync_api import sync_playwright
    W = load_engine()
    import edufine_common as E
    say("🔐  에듀파인 로그인 확인 중…")
    W.ensure_chrome(SITE, minimized=False)
    with sync_playwright() as p:
        ctx = W.connect_sync(p, W.SITES[SITE]["port"]).contexts[0]
        page = edufine_page(ctx, W, E)
        say("📂  %s 여는 중…" % label)
        edufine_open(page, E, W, menu_id)
    say("✅  열었습니다: %s" % label)
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    a = sys.argv[1:]
    if a[:1] == ["open-neis"] and len(a) >= 2:
        return cmd_open_neis(a[1], a[2] if len(a) > 2 else "나이스 메뉴")
    if a[:1] == ["open-edufine"] and len(a) >= 2:
        return cmd_open_edufine(a[1], a[2] if len(a) > 2 else "에듀파인 메뉴")
    say("❌  사용법: open-neis <경로> <이름> | open-edufine <메뉴ID> <이름>")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("❌  " + msg, flush=True)
        sys.exit(1)
