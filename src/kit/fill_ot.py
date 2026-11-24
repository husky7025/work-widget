# -*- coding: utf-8 -*-
"""업무위젯 «초과근무 신청» — 나이스 복무 › 개인초과근무관리 › 신청(초과근무신청 창)의 칸을 채워 둔다. 승인요청(상신)은 누르지 않는다.

  python fill_ot.py --kind "시간외 근무" --date 2026-11-25 --start 16:00 --end 22:00 --task "자율학습감독 및 학생생활지도"
  python fill_ot.py ... --date 2026-11-25,2026-11-26,2026-11-28 --holiday-dates 2026-11-28     여러 날 (날마다 한 줄)

· 한 날짜마다: 초과근무일자 → 종별 → (휴일이면 «휴일» 체크) → 시작·종료 시/분 → 하여야 할 일.
· 여러 날이면 둘째 날부터 [행추가]로 줄을 늘리고 그 줄을 같은 값으로 채운다.
  [행추가]는 다음 날 날짜·16:00~21:00 으로 새 줄을 만들고 «하여야 할 일»은 비운다 (2026-11-24 실측) → 줄마다 모두 다시 넣는다.
  (위쪽 «시작일자~종료일자 [추가]»는 지금 줄의 할 일이 비어 있으면 막히고, 띄엄띄엄한 날짜는 못 넣어서 쓰지 않는다)
· «초과근무시간 합»은 나이스가 셈한다 (평일 1시간 차감 등). 휴일 초과근무는 전날 18시 전에 올려야 사전신청으로 인정된다.
· 종별 «휴일 근무»는 휴일근무가 제도화된 공무원만 — 보통 선생님의 주말 근무는 «시간외 근무 + 휴일 체크» (고르면 나이스가 안내를 띄운다)
· 결재선·승인요청은 선생님이 직접.
"""
import argparse
import re
import sys

import work_widget_fill as F

KINDS = ["시간외 근무", "야간 근무", "휴일 근무"]
ROWS_JS = r"""(d) => { const g = d.querySelector('[role=grid][aria-label="초과근무신청목록"]'); if (!g) return [];
  return [...g.querySelectorAll('[role=row]')].map(r => [...r.querySelectorAll('[role=gridcell]')].map(c => (c.innerText||'').trim()))
    .filter(c => c.length > 2 && /\d{4}-\d{2}-\d{2}/.test(c.join(' '))); }"""


async def fill_row(page, dlg, a, day, holiday, sh, sm, eh, em):
    """지금 고른 줄(아래쪽 입력 칸)을 채운다. 그 줄의 «초과근무시간 합»을 돌려준다."""
    await F.put(page, dlg.locator('input[aria-label="초과근무일자"]').first, day)
    await F.after_notice(page)
    await F.pick(page, dlg.locator('[role="combobox"][aria-label^="초과근무종별"]').first, a.kind)
    await F.after_notice(page)
    box = dlg.locator('[role="checkbox"][aria-label="휴일 선택"]').first
    if ((await box.get_attribute("aria-checked")) == "true") != holiday:      # 화면 안내: 휴일이면 «반드시 휴일 체크를 하신 뒤 시간 선택»
        await box.evaluate("e => e.click()")       # 체크박스는 칸이 넓어 가운데를 누르면 안 먹는다 (키트 나이스출장 스킬)
        await page.wait_for_timeout(600)
        await F.after_notice(page)
    if ((await box.get_attribute("aria-checked")) == "true") != holiday:
        raise RuntimeError("%s «휴일» 칸이 맞게 안 됐어요 — 나이스 창에서 직접 고쳐 주세요" % day)
    for label, v in (("신청시작시", sh), ("신청시작분", sm), ("신청종료시", eh), ("신청종료분", em)):
        await F.put(page, dlg.locator('input[aria-label="%s"]' % label).first, "%02d" % v)
    await F.after_notice(page)
    await F.put(page, dlg.locator('textarea[aria-label="하여야 할 일"]').first, a.task)
    got = await dlg.locator('input[aria-label="초과근무일자"]').first.input_value()
    if got != day:
        raise RuntimeError("날짜가 제대로 안 들어갔어요 (%s) — 나이스 창에서 달력으로 고쳐 주세요" % got)
    h = await dlg.locator('input[aria-label="초과근무시간 합 시"]').first.input_value()
    m = await dlg.locator('input[aria-label="초과근무시간 합 분"]').first.input_value()
    return int(h or 0) * 60 + int(m or 0)


async def run(a):
    days = [d.strip() for d in a.date.split(",") if d.strip()]
    if not days or not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in days):
        raise RuntimeError("날짜는 2026-11-25 처럼 적어 주세요 (여러 날은 쉼표로)")
    if len(set(days)) != len(days):
        raise RuntimeError("같은 날짜가 두 번 들어 있어요")
    days.sort()
    hol = {d.strip() for d in a.holiday_dates.split(",") if d.strip()} | (set(days) if a.holiday else set())
    if not all(re.fullmatch(r"\d{1,2}:\d{2}", t) for t in (a.start, a.end)):
        raise RuntimeError("시각은 13:00 처럼 적어 주세요")
    (sh, sm), (eh, em) = F.hm(a.start), F.hm(a.end)
    if (eh, em) <= (sh, sm):
        raise RuntimeError("끝나는 시각이 시작보다 늦어야 해요")
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        page, dlg = await F.open_dialog(p, "개인초과근무관리", "초과근무신청")
        total, per = 0, []
        for i, day in enumerate(days):
            if i:                                    # 둘째 날부터 — 앞 줄을 다 채운 뒤 [행추가]
                before = len(await dlg.evaluate(ROWS_JS))
                await F.MB.click(page, dlg.get_by_text("행추가", exact=True).first, timeout=8000)
                await page.wait_for_timeout(1500)
                await F.after_notice(page)
                if len(await dlg.evaluate(ROWS_JS)) != before + 1:
                    raise RuntimeError("%s 줄을 더하지 못했어요 (행추가) — 앞의 %d일은 채워져 있어요" % (day, i))
            print("📝  %s 채우는 중 (%d/%d)" % (day, i + 1, len(days)), flush=True)
            mins = await fill_row(page, dlg, a, day, day in hol, sh, sm, eh, em)
            total += mins
            per.append(mins)
        rows = await dlg.evaluate(ROWS_JS)
        got = sorted(c for r in rows for c in r if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c))
        if got != days:
            raise RuntimeError("나이스 목록의 날짜가 고른 날과 달라요 (%s) — 나이스 창에서 확인해 주세요" % ", ".join(got))
        hm_ = "%02d시간 %02d분" % (total // 60, total % 60)
        if len(days) == 1:
            return "초과근무시간 합 " + hm_
        return "%d일 · 초과근무시간 합 모두 %s" % (len(days), hm_)


def main():
    ap = argparse.ArgumentParser(description="나이스 초과근무신청 칸 채우기 (상신 안 함)")
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--date", required=True, help="YYYY-MM-DD — 여러 날은 쉼표로 (날마다 한 줄)")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--holiday", action="store_true", help="모든 날을 휴일로 — «휴일» 칸에 체크")
    ap.add_argument("--holiday-dates", default="", help="휴일로 체크할 날짜들 (쉼표로)")
    return F.run_main(run, ap, "초과근무신청 칸을 채웠습니다 — 시간 합을 확인하고 [승인요청]은 직접 눌러 주세요")


if __name__ == "__main__":
    sys.exit(main())
