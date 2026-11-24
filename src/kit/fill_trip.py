# -*- coding: utf-8 -*-
"""업무위젯 «출장 신청» — 나이스 복무 › 개인출장관리 › 신청(출장신청 창)의 칸을 채워 둔다. 승인요청(상신)은 누르지 않는다.

  python fill_trip.py --kind "국내출장(관내)" --date 2026-12-01 [--end-date 2026-12-01] --start 15:00 --end 17:00 --place 교육정보연수원 --purpose 직무연수

· 날짜 → 시각 → 출장종류 → 출장지·출장목적 차례로 넣는다.
· 하루 안의 몇 시간짜리인데 나이스가 «1일 ○시간»으로 셈하면 «0일 ○시간 ○분»으로 고친다 (키트 나이스출장 스킬 4절 · 2026-11-24 실측 기본값 1일 0시간).
  8시간 이상이거나 여러 날이면 나이스 셈을 그대로 둔다.
· 결재선·승인요청은 선생님이 직접.
"""
import argparse
import sys

import work_widget_fill as F

KINDS = ["국내출장(관내)", "국내출장(관외)", "출장(연수)", "국외출장"]
ROW = "1행 마지막 행 "


async def run(a):
    err = F.check_args(a, need_end_date=True)
    if err:
        raise RuntimeError(err)
    end_date = a.end_date or a.date
    if end_date < a.date:
        raise RuntimeError("끝나는 날짜가 시작보다 빨라요")
    (sh, sm), (eh, em) = F.hm(F.MB.round_to_step(a.start)), F.hm(F.MB.round_to_step(a.end))
    if end_date == a.date and (eh, em) <= (sh, sm):
        raise RuntimeError("끝나는 시각이 시작보다 늦어야 해요")
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        page, dlg = await F.open_dialog(p, "개인출장관리", "출장신청")
        grid = dlg.locator('[role="grid"][aria-label="기간정보 목록 그리드"]')
        # 1) 기간 — 시작일자를 바꾸면 종료일자가 따라오므로 시작 먼저
        await F.put(page, grid.locator('input[aria-label^="%s시작일자"]' % ROW).first, a.date)
        await F.put(page, grid.locator('input[aria-label^="%s종료일자"]' % ROW).first, end_date)
        for label, v in (("시작시간", sh), ("시작분", sm), ("종료시간", eh), ("종료분", em)):
            await F.pick(page, grid.locator('[role="combobox"][aria-label^="%s%s"]' % (ROW, label)).first, "%02d" % v)
        got = [await grid.locator('input[aria-label^="%s%s"]' % (ROW, k)).first.input_value() for k in ("시작일자", "종료일자")]
        if got != [a.date, end_date]:
            raise RuntimeError("날짜가 제대로 안 들어갔어요 (%s ~ %s) — 나이스 창에서 달력으로 고쳐 주세요" % tuple(got))
        # 2) 신청시간 — 하루 안의 몇 시간이면 «0일 ○시간 ○분»
        spin = {k: grid.locator('[role="spinbutton"][aria-label*="신청시간  %s"]' % k).first for k in ("일", "시간", "분")}
        mins = (eh * 60 + em) - (sh * 60 + sm)
        if end_date == a.date and mins < 8 * 60:
            for k, v in (("일", 0), ("시간", mins // 60), ("분", mins % 60)):
                await F.put(page, spin[k], str(v))
        days = [await spin[k].input_value() for k in ("일", "시간", "분")]
        # 3) 출장종류 · 출장지 · 출장목적
        await F.pick(page, dlg.locator('[role="combobox"][aria-label^="출장종류"]').first, a.kind)
        # 출장(연수)를 고르면 «여비부지급의 경우 에듀파인으로 연계되지 않습니다» 안내가 뜬다 (2026-11-24 실측) — 안내라서 [확인]
        await F.after_notice(page, ok_texts=("여비부지급",))
        # 연락처 (필수) — 이 창의 틀은 ___-____-____ 라 숫자만 한 글자씩 넣는다 (근무상황신청의 (___)____-____ 와 다르다)
        digits = "".join(ch for ch in (a.contact or F.MB.teacher_config.load_config().get("contact") or "") if ch.isdigit())
        if digits:
            box = dlg.locator('input[aria-label="연락처"]').first
            await box.scroll_into_view_if_needed()
            await box.focus()                 # 이 칸 위에 cl-overlay 가 덮여 있어 click 은 막힌다 (2026-11-24 실측) — focus 후 키보드로
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Delete")
            await page.keyboard.type(digits, delay=60)
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(300)
        await F.put(page, dlg.locator('input[aria-label="출장지"]').first, a.place)
        await F.put(page, dlg.locator('input[aria-label="출장목적"]').first, a.purpose)
        return "신청시간 %s일 %s시간 %s분" % tuple(days)


def main():
    ap = argparse.ArgumentParser(description="나이스 출장신청 칸 채우기 (상신 안 함)")
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--date", required=True)
    ap.add_argument("--end-date", default="")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--place", required=True)
    ap.add_argument("--purpose", required=True)
    ap.add_argument("--contact", default="")
    return F.run_main(run, ap, "출장신청 칸을 채웠습니다 — 결재선 확인 뒤 [승인요청]은 직접 눌러 주세요")


if __name__ == "__main__":
    sys.exit(main())
