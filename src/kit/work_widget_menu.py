# -*- coding: utf-8 -*-
"""업무위젯 «펼침 메뉴» — 나이스·K-에듀파인의 하위 메뉴 화면 하나를 연다.

  python work_widget_menu.py read                         내 나이스·에듀파인 메뉴 목록을 읽어 work_widget_menus.json 에 적는다
  python work_widget_menu.py open-neis '<경로 JSON>' 이름     예) '[["복무",0],["개인근무상황관리",1]]'
  python work_widget_menu.py open-edufine <메뉴ID> 이름       예) A00AAB0106001 (기안한문서)

사람이 메뉴를 누르는 것과 같다 — 나이스는 메뉴 글자를 차례로 누르고, 에듀파인은 사람이 메뉴를 누를 때 에듀파인이 부르는
gfnOpenMenu(메뉴ID) 를 그대로 부른다 (권한 없는 메뉴는 에듀파인 메뉴 표에 없으므로 열리지 않는다).
화면을 열기만 하고 신청·저장·결재·상신은 누르지 않는다.
메뉴 목록은 선생님마다(역할·권한) 다르므로 각자 PC 에서 read 로 읽는다 — 나이스·에듀파인이 들고 있는 메뉴 표만 읽고 화면은 옮기지 않는다.
로그인은 open_neis.py · 에듀파인 키트 로그인을 그대로 쓴다 (인증서 암호는 keyring, 이 파일은 다루지 않는다).
"""
import asyncio
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

MENUS_FILE = HERE / "work_widget_menus.json"
SITE = "edufine"                       # 나이스·에듀파인 모두 위젯 크롬(포트 9324) 한 개를 쓴다

EDU_APP_JS = r"""() => { try { const a = nexacro.getApplication(); return !!(a && a.gdsMenu && a.gdsMenu.getRowCount() > 0); } catch (e) { return false; } }"""
EDU_OPEN_JS = r"""(id) => { const a = nexacro.getApplication(), fs = a.mainframe.MainVFrameSet.frames;
  let f = null; for (let i = 0; i < fs.length; i++) { const x = fs[i]; if (x && x.form && typeof x.form.gfnOpenMenu === 'function') { f = x.form; if (x.name === 'TopFrame') break; } }
  if (!f) return 'nofn';
  a.gdsMenu.filter('');
  if (a.gdsMenu.findRow('menuId', id) < 0) return 'nomenu';
  f.gfnOpenMenu(id); return 'ok'; }"""
EDU_STATE_JS = r"""(id) => { const a = nexacro.getApplication(), d = a.gdsOpenMenu;
  let open = false; for (let r = 0; r < d.getRowCount(); r++) if (d.getColumn(r, a.gv_menuIdCol) === id) open = true;
  return {n: d.getRowCount(), max: Number(a.gv_openMaxFrame || 0), open: open}; }"""
EDU_OVERLAY = "#nexacontainer.nexamodaloverlay"
# 나이스: 신청서 같은 입력 창은 .cl-dialog (로그인 직후 공지는 .cl-aside 라 따로 닫는다)
NEIS_DIALOG_JS = r"""() => [...document.querySelectorAll('.cl-dialog')].filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden').map(e => {
  const h = e.querySelector('.cl-dialog-header'); return ((h && h.innerText) || '').trim().slice(0, 30); })"""
EDU_MENU_JS = r"""() => { const a = nexacro.getApplication(), ds = a.gdsMenu, o = [];
  ds.filter('');
  const cols = ['menuId', 'upperMenuId', 'menuNm', 'leafYn', 'indictYn'];
  for (let r = 0; r < ds.getRowCount(); r++) { const x = {}; cols.forEach(c => { const v = ds.getColumn(r, c); x[c] = (v == null ? '' : String(v)); }); o.push(x); }
  return o; }"""
NEIS_MENU_JS = r"""() => { const a = cpr.core.Platform.INSTANCE.getAllRunningAppInstances().find(x => x.app.id === 'app/com/main/Index');
  if (!a) return null;
  const rows = (name) => { const ds = a.lookup(name), o = []; if (!ds) return o;
    for (let r = 0; r < ds.getRowCount(); r++) { const x = ds.getRowData(r);
      o.push({id: String(x.MENU_ID || ''), nm: String(x.MENU_NM || '').trim(), up: String(x.UP_MENU_ID || '')}); }
    return o; };
  return {all: rows('dsAllMenu'), base: rows('dsBaseMenu')}; }"""
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


def neis_read(page):
    """나이스 메뉴 → [{group, path:[[이름,단계]…], name, crumb}]. 나이스가 들고 있는 메뉴 표만 읽는다 (화면은 그대로).
    나의메뉴(dsBaseMenu): 복무·급여 같은 0단계 › 1단계(화면).
    역할 메뉴(dsAllMenu): 역할(0단계) › 분류(화면에 안 보임) › 2단계 › 3단계(화면). 3단계 밑은 화면 안의 탭이라 3단계까지만."""
    d = page.evaluate(NEIS_MENU_JS)
    if not d:
        raise RuntimeError("나이스 메뉴 표를 찾지 못했습니다 (나이스 첫 화면이 열려 있는지 확인하세요)")
    out = []
    base = {}
    for r in d["base"]:
        base.setdefault(r["id"], r)
    has_kid = {r["up"] for r in base.values()}
    for r in base.values():
        par = base.get(r["up"])
        if par is not None and par["up"] not in base:
            out.append({"group": "나의메뉴", "path": [[par["nm"], 0], [r["nm"], 1]], "name": r["nm"], "crumb": par["nm"]})
        elif par is None and r["id"] not in has_kid:            # 혼자 있는 0단계 (예: 직무관련외부활동신청)
            out.append({"group": "나의메뉴", "path": [[r["nm"], 0]], "name": r["nm"], "crumb": ""})
    # 같은 메뉴가 여러 역할 밑에 겹쳐 있다 (예: 창의적체험활동) → 표 순서대로, 바로 앞에 나온 부모 줄에 잇는다
    rows = d["all"]
    parent, last = [], {}
    for i, r in enumerate(rows):
        parent.append(last.get(r["up"]))
        last[r["id"]] = i
    has_kid = {parent[i] for i in range(len(rows)) if parent[i] is not None}
    for i, r in enumerate(rows):
        ch, j = [r], parent[i]
        while j is not None and len(ch) < 8:
            ch.insert(0, rows[j])
            j = parent[j]
        if len(ch) == 4:
            role, _, l2, l3 = ch
            out.append({"group": role["nm"], "path": [[role["nm"], 0], [l2["nm"], 2], [l3["nm"], 3]], "name": l3["nm"], "crumb": l2["nm"]})
        elif len(ch) == 3 and i not in has_kid:
            role, _, l2 = ch
            out.append({"group": role["nm"], "path": [[role["nm"], 0], [l2["nm"], 2]], "name": l2["nm"], "crumb": ""})
    seen, uniq = set(), []
    for m in out:
        k = json.dumps(m["path"], ensure_ascii=False)
        if k not in seen:
            seen.add(k)
            uniq.append(m)
    return uniq


def neis_busy_dialog(page):
    """선생님이 띄워 둔 입력 창(신청서 등)이 있으면 그 제목. 있으면 화면을 옮기지 않는다 (쓰던 내용이 날아가지 않게)."""
    try:
        titles = page.evaluate(NEIS_DIALOG_JS)
    except Exception:
        return None
    return (titles[0] or "입력 창") if titles else None


def neis_open(page, path):
    busy = neis_busy_dialog(page)
    if busy:
        raise RuntimeError("나이스에 «%s» 창이 열려 있어요 — 쓰던 내용을 마치거나 닫은 뒤 다시 눌러 주세요" % busy)
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
    fresh = page is None
    if fresh:
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
    if fresh:                                   # 방금 로그인한 탭만 공지 팝업을 닫는다
        E.close_modals(page)
    elif page.locator(EDU_OVERLAY).count():     # 쓰던 탭에 팝업이 떠 있으면 건드리지 않는다 (작성 중일 수 있다)
        raise RuntimeError("에듀파인에 열린 창(팝업)이 있어요 — 마치거나 닫은 뒤 다시 눌러 주세요")
    return page


def edufine_read(page):
    """에듀파인 메뉴 → [{group, id, name, crumb}]. 권한 있는 메뉴만 메뉴 표에 있다. 숨김 메뉴는 뺀다."""
    rows = page.evaluate(EDU_MENU_JS)
    by_id = {}
    for r in rows:
        by_id.setdefault(r["menuId"], r)
    out, seen = [], set()
    for r in rows:
        if r["leafYn"] != "Y" or r["indictYn"] == "N" or r["menuId"] in seen:
            continue
        chain, up, hidden = [], by_id.get(r["upperMenuId"]), False
        while up is not None and len(chain) < 8:
            hidden = hidden or up["indictYn"] == "N"
            chain.insert(0, up["menuNm"])
            up = by_id.get(up["upperMenuId"])
        if hidden or not chain:
            continue
        seen.add(r["menuId"])
        out.append({"group": chain[0], "id": r["menuId"], "name": r["menuNm"], "crumb": " › ".join(chain[1:])})
    return out


def edufine_open(page, E, W, menu_id):
    st = page.evaluate(EDU_STATE_JS, menu_id)
    if not st["open"] and st["max"] and st["n"] >= st["max"]:
        raise RuntimeError("에듀파인 탭이 가득 찼어요 (%d개) — 아래쪽 안 쓰는 탭을 닫고 다시 눌러 주세요" % st["n"])
    r = page.evaluate(EDU_OPEN_JS, menu_id)
    if r == "nomenu":
        raise RuntimeError("에듀파인에서 이 메뉴 권한이 없습니다")
    if r != "ok":
        raise RuntimeError("에듀파인 메뉴 열기 기능을 찾지 못했습니다")
    for _ in range(30):
        page.wait_for_timeout(500)
        if ("_%s_" % menu_id) in page.evaluate(EDU_ACTIVE_JS):
            break
    W.to_front_sync(page)


# ── 명령 ─────────────────────────────────────────────────
def cmd_read():
    from playwright.sync_api import sync_playwright
    W = load_engine()
    import edufine_common as E
    say("🔐  나이스 로그인 확인 중…")
    neis_login()
    with sync_playwright() as p:
        ctx = W.connect_sync(p, W.SITES[SITE]["port"]).contexts[0]
        npg = neis_page(ctx)
        if npg is None:
            raise RuntimeError("나이스 탭을 찾지 못했습니다")
        say("📋  나이스 메뉴 읽는 중…")
        neis = neis_read(npg)
        say("🔐  에듀파인 로그인 확인 중…")
        epg = edufine_page(ctx, W, E)
        say("📋  에듀파인 메뉴 읽는 중…")
        edu = edufine_read(epg)
    if not neis and not edu:
        raise RuntimeError("메뉴를 하나도 읽지 못했습니다")
    MENUS_FILE.write_text(json.dumps({"read_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "neis": neis, "edufine": edu},
                                     ensure_ascii=False, indent=1), encoding="utf-8")
    say("✅  메뉴를 읽었습니다 (나이스 %d개 · 에듀파인 %d개)" % (len(neis), len(edu)))
    return 0


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
    if a[:1] == ["read"]:
        return cmd_read()
    if a[:1] == ["open-neis"] and len(a) >= 2:
        return cmd_open_neis(a[1], a[2] if len(a) > 2 else "나이스 메뉴")
    if a[:1] == ["open-edufine"] and len(a) >= 2:
        return cmd_open_edufine(a[1], a[2] if len(a) > 2 else "에듀파인 메뉴")
    say("❌  사용법: read | open-neis <경로> <이름> | open-edufine <메뉴ID> <이름>")
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
