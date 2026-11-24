# -*- coding: utf-8 -*-
"""업무위젯 «나이스 칸 채우기» 공통 — 위젯 크롬(포트 9324)으로 로그인한 나이스에서 복무 메뉴 화면의 [신청] 창을 연다.

fill_trip.py(출장) · fill_ot.py(초과근무)가 쓴다. 칸을 채우는 도구만 있고, 승인요청·저장·상신을 누르는 코드는 없다.
콤보 고르기·글자 넣기는 키트 main_bokmu.py 의 것을 그대로 쓴다 (나이스 eXbuilder 화면에서 검증된 것).
"""
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))

import main_bokmu as MB          # noqa: E402  select_combo_option · fill_text_input · click 만 쓴다

DIALOGS_JS = """() => [...document.querySelectorAll('.cl-dialog')]
  .filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden').length"""


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hm(t):
    """'13:00' → (13, 0)"""
    h, m = t.split(":")
    return int(h), int(m)


def check_args(a, need_end_date=False):
    """날짜·시각 꼴 검사. 틀리면 안내 글을 돌려준다 (맞으면 None)."""
    dates = [a.date] + ([a.end_date] if need_end_date and a.end_date else [])
    if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in dates):
        return "날짜는 2026-11-25 처럼 적어 주세요"
    if not all(re.fullmatch(r"\d{1,2}:\d{2}", t) for t in (a.start, a.end)):
        return "시각은 13:00 처럼 적어 주세요"
    return None


async def open_dialog(p, menu, dialog_label):
    """로그인 → 나이스 첫 화면 → 복무 › menu → [신청] → dialog_label 창. (page, dialog) 를 돌려준다."""
    import neis_session as N
    on = load("open_neis", HERE / "open_neis.py")
    W = on.load_engine()
    await on.run()                       # 이미 로그인된 나이스 탭이 있으면 그 탭을 앞으로
    browser = await W.connect_async(p, W.SITES["edufine"]["port"])
    ctx = browser.contexts[0]
    page = None
    for pg in ctx.pages:
        if ".neis.go.kr" in pg.url and await N.is_logged_in(pg):
            page = pg
            break
    if page is None:
        raise RuntimeError("로그인된 나이스 창을 찾지 못했습니다")
    await page.bring_to_front()
    if await page.evaluate(DIALOGS_JS):
        raise RuntimeError("나이스에 열려 있는 입력 창이 있어요 — 마치거나 닫은 뒤 다시 눌러 주세요")
    logo = page.locator('[aria-label="나이스로고"]').first       # 복무 메뉴(나의메뉴)는 첫 화면에만 보인다
    if await logo.count():
        await logo.click()
        await page.wait_for_timeout(2500)
    await MB.neis.dismiss_notice_popup(page, timeout=2000)
    print("📝  %s 창을 여는 중…" % dialog_label, flush=True)
    await MB.click(page, page.locator("a").filter(has_text="복무 0단계 메뉴항목").first, timeout=8000)
    await page.wait_for_timeout(700)
    await MB.click(page, page.locator("a").filter(has_text="%s 1단계" % menu).first, timeout=8000)
    await page.wait_for_timeout(2000)
    await MB.wait_loading(page, 60)
    btns = page.get_by_text("신청", exact=True)
    for i in range(await btns.count()):
        if await btns.nth(i).is_visible():
            await MB.click(page, btns.nth(i), timeout=5000)
            break
    else:
        raise RuntimeError("«신청» 단추를 찾지 못했습니다 (%s 화면)" % menu)
    dialog = page.locator('[role="dialog"][aria-label="%s"]' % dialog_label)
    await dialog.wait_for(state="visible", timeout=15_000)
    await page.wait_for_timeout(1500)
    await MB.wait_loading(page, 60)
    return page, dialog


async def put(page, loc, value):
    """칸에 값을 넣고 Tab 으로 빠져나온다 (나이스가 값을 받아 다른 칸을 다시 계산하게)."""
    try:
        await MB.fill_text_input(page, loc, value)
    except Exception as e:                       # 칸 위를 cl-overlay 가 덮고 있으면 click 이 막힌다 → focus 후 키보드로
        if "Timeout" not in str(e) and "intercepts" not in str(e):
            raise
        await loc.scroll_into_view_if_needed()
        await loc.focus()
        await page.keyboard.press("Control+a")
        await page.keyboard.type(value, delay=20)
    await loc.press("Tab")
    await page.wait_for_timeout(400)


async def pick(page, combo, text):
    await MB.select_combo_option(page, combo, text)
    await page.wait_for_timeout(400)


MSG_BOX = '[role="dialog"].modal-msg'


async def after_notice(page, ok_texts=()):
    """칸을 고른 뒤 나이스가 띄우는 알림창. 안내만 하는 것(ok_texts 의 글자가 든 것)이면 [확인]을 누르고,
    모르는 알림이면 누르지 않고 그 글자로 멈춘다 (승인요청·저장 확인창일 수도 있으니 아무거나 누르지 않는다)."""
    await page.wait_for_timeout(500)
    box = page.locator(MSG_BOX)
    for _ in range(3):
        if not await box.count() or not await box.last.is_visible():
            return
        text = re.sub(r"\s+", " ", await box.last.inner_text()).strip()
        if not any(t in text for t in ok_texts):
            raise RuntimeError("나이스 알림: %s — 나이스 창에서 확인해 주세요" % text[:100])
        print("ℹ️  나이스 안내: %s" % text[:80], flush=True)
        await box.last.get_by_text("확인", exact=True).last.click(timeout=5000)
        await page.wait_for_timeout(600)


def run_main(coro_fn, parser, done_msg):
    """명령줄 → 실행 → 끝 글자. 위젯은 «❌ …» 줄과 done_msg 가 든 줄을 읽는다."""
    import asyncio
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    a = parser.parse_args()
    try:
        summary = asyncio.run(coro_fn(a))
    except BaseException as e:
        if isinstance(e, SystemExit):
            raise
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("❌  " + msg, flush=True)
        return 1
    print("✅  %s%s" % (done_msg, (" (" + summary + ")") if summary else ""), flush=True)
    return 0
