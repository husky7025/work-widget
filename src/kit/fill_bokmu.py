# -*- coding: utf-8 -*-
"""업무위젯 «복무 신청» — 나이스 개인근무상황관리의 근무상황신청 창을 열고 칸을 채워 둔다. 승인요청(상신)은 누르지 않는다.

  python fill_bokmu.py --type 조퇴 --date 2026-11-25 --start 13:00 --end 16:00 --reason 개인용무 [--contact 010-…] [--child 이름] [--over8]

채우기는 키트 main_bokmu.py 의 open_gwn_apply_modal · fill_work_sittn_form 을 그대로 쓴다 (나이스 화면이 바뀌면 키트와 함께 고친다).
상신 함수(submit)는 부르지도, 가져오지도 않는다 — 선생님이 창을 눈으로 보고 결재선을 고른 뒤 직접 [승인요청]을 누른다.
로그인·창은 open_neis.py 와 같은 위젯 크롬(포트 9324)을 쓰고, 끝나도 창을 닫지 않는다.
"""
import argparse
import asyncio
import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "widget"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def run(a):
    from playwright.async_api import async_playwright
    import main_bokmu as MB          # 채우기 함수만 쓴다 (submit 은 쓰지 않는다)
    import neis_session as N
    on = load("open_neis", HERE / "open_neis.py")
    W = on.load_engine()

    await on.run()                   # 인증서 로그인 (이미 로그인된 나이스 탭이 있으면 그 탭을 앞으로)
    async with async_playwright() as p:
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
        # 선생님이 쓰던 신청서 등이 열려 있으면 건드리지 않는다
        busy = await page.evaluate("""() => [...document.querySelectorAll('.cl-dialog')]
            .filter(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden').length""")
        if busy:
            raise RuntimeError("나이스에 열려 있는 입력 창이 있어요 — 마치거나 닫은 뒤 다시 눌러 주세요")
        # 복무 메뉴(나의메뉴)는 나이스 첫 화면에만 보인다
        logo = page.locator('[aria-label="나이스로고"]').first
        if await logo.count():
            await logo.click()
            await page.wait_for_timeout(2500)
        await MB.neis.dismiss_notice_popup(page, timeout=2000)
        print("📝  근무상황신청 창을 여는 중…", flush=True)
        dialog = await MB.open_gwn_apply_modal(page)
        extra = {"child": a.child or None, "over8": a.over8} if a.type == "육아시간" else {}   # 옛 키트에는 이 인자가 없다
        await MB.fill_work_sittn_form(page, dialog, sittn_type=a.type, d=date.fromisoformat(a.date),
                                      start_hm=a.start, end_hm=a.end, reason=a.reason,
                                      contact=a.contact or MB.teacher_config.load_config().get("contact") or None, **extra)
        rep = ""
        if a.end_date and a.end_date != a.date:
            # 여러 날 «매일 같은 시각» — 종료일자를 바꾸고 «일 반복»에 체크하면 나이스가 «○일 매 ○시간 ○분»으로 셈한다.
            # 주말은 나이스가 뺀다 (2026-11-24 실측: 11-25 수 ~ 11-30 월 → 4일). 체크박스는 칸이 넓어 요소에 click() 을 직접 건다.
            end_box = dialog.locator('input[aria-label="신청기간 종료일자"]').first
            await MB.fill_text_input(page, end_box, a.end_date)
            await end_box.press("Tab")
            await page.wait_for_timeout(1000)
            if await end_box.input_value() != a.end_date:
                raise RuntimeError("끝 날짜가 제대로 안 들어갔어요 — 나이스 창에서 달력으로 고쳐 주세요")
            box = dialog.locator('[role="checkbox"][aria-label="일 반복"]').first
            if (await box.get_attribute("aria-disabled")) == "true":
                raise RuntimeError("이 근무상황은 나이스에서 «일 반복»을 쓸 수 없어요 — 날짜마다 따로 신청해 주세요")
            if (await box.get_attribute("aria-checked")) != "true":
                await box.evaluate("e => e.click()")
                await page.wait_for_timeout(1200)
            if (await box.get_attribute("aria-checked")) != "true":
                raise RuntimeError("«일 반복»에 체크가 안 됐어요 — 나이스 창에서 직접 체크해 주세요")
            rep = " 매"
        spin = [await dialog.locator('[role="spinbutton"][aria-label="%s"]' % k).first.input_value() for k in ("일", "시간", "분")]
        return "신청시간 %s일%s %s시간 %s분" % (spin[0], rep, spin[1], spin[2])
        # 여기서 끝 — 승인요청은 선생님이 직접. 크롬·탭은 그대로 두고 연결만 끊는다.


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="나이스 근무상황신청 칸 채우기 (상신 안 함)")
    ap.add_argument("--type", required=True, choices=["조퇴", "외출", "지각", "병조퇴", "병외출", "병지각", "육아시간"])
    ap.add_argument("--date", required=True)
    ap.add_argument("--end-date", default="", help="여러 날이면 끝 날짜 — 매일 같은 시각으로 «일 반복»")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--contact", default="")
    ap.add_argument("--child", default="")
    ap.add_argument("--over8", action="store_true")
    a = ap.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date) or not all(re.fullmatch(r"\d{1,2}:\d{2}", t) for t in (a.start, a.end)):
        print("❌  날짜는 2026-11-25, 시각은 13:00 처럼 적어 주세요", flush=True)
        return 1
    mins = [int(h) * 60 + int(m) for h, m in (t.split(":") for t in (a.start, a.end))]
    if mins[1] <= mins[0]:
        print("❌  끝나는 시각이 시작보다 늦어야 해요", flush=True)
        return 1
    if a.end_date and (not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.end_date) or a.end_date < a.date):
        print("❌  끝 날짜가 시작보다 빨라요", flush=True)
        return 1
    try:
        summary = asyncio.run(run(a))
    except BaseException as e:
        if isinstance(e, SystemExit):
            raise
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("❌  " + msg, flush=True)
        return 1
    print("✅  근무상황신청 칸을 채웠습니다 — 결재선 확인 뒤 [승인요청]은 직접 눌러 주세요" + (" (%s)" % summary if summary else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
