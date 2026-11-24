# -*- coding: utf-8 -*-
"""교육행정데이터통합관리 «데이터취합(기관접수대기 N · 내담당 M)» 의 기관접수대기 숫자를 읽어 한 줄로 찍는다. 읽기 전용.

위젯 전용 크롬(포트 9324)에서
  - 통합관리 탭이 있으면 그 탭을 새로고침해서 읽고 (새로고침이 접속 시간 60분도 늘려 준다)
  - 없으면 업무포털 메인 탭이 있을 때만 «데이터취합» 링크 주소로 뒤쪽(앞으로 꺼내지 않음) 새 탭을 열어 읽는다.
새 로그인·접수·제출·클릭은 하지 않는다. 읽지 못하면 숫자를 지어내지 않고 이유만 찍는다 (종료 코드 1).
출력(마지막 줄): JEOPSU {"wait": N}
"""
import json
import re
import sys
import urllib.request

PORT = 9324
SCREEN = "in/dam/apm/wm/in_dam_apmwm01_m01&agrtChcGbn=1"
COUNT_JS = r"""() => { const m = (document.body && document.body.innerText || '').match(/기관접수대기\s*\(?\s*(\d+)/); return m ? m[1] : null }"""


def stable_count(page, tries=40):
    """화면이 뜰 때 잠깐 «기관접수대기 0» 이 보였다가 진짜 숫자로 바뀐다 (0.1초쯤, 2026-11-17 실측)
    → 같은 숫자가 0.5초 간격으로 세 번 연달아 나와야 믿는다. 최대 약 20초."""
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


class Fail(Exception):
    """숫자를 못 읽은 이유 (지어내지 않고 이유만 알린다)."""


def fail(msg):
    print("❌  " + msg, flush=True)
    sys.exit(1)


def chrome_up():
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=3).read()
        return True
    except Exception:
        return False


def read(browser):
    """이미 연결한 위젯 크롬에서 기관접수대기 숫자를 읽는다 → {"wait": N}. 못 읽으면 Fail."""
    pages = [pg for ctx in browser.contexts for pg in ctx.pages]
    page = next((pg for pg in pages if re.search(r"edmgr\.kr/taskPotlMain", pg.url)), None) \
        or next((pg for pg in pages if "edmgr.kr" in pg.url), None)
    portal = next((pg for pg in pages if "bpm_man_mn00_001" in pg.url), None)
    if page is not None:
        page.set_default_timeout(20_000)
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception:
            raise Fail("통합관리 화면 새로고침에 실패했습니다")
    elif portal is not None:
        m = re.match(r"https://([a-z]+)\.eduptl\.kr", portal.url)
        if not m:
            raise Fail("업무포털 주소에서 지역을 알아내지 못했습니다")
        # 뒤쪽 탭으로 연다 (background=True — 선생님이 보던 탭·창을 빼앗지 않는다)
        url = "https://%s.edmgr.kr/taskPotl?edmgrUrl=%s" % (m.group(1), SCREEN)
        ctx = portal.context
        with ctx.expect_page(timeout=20_000) as info:
            browser.new_browser_cdp_session().send("Target.createTarget", {"url": url, "background": True})
        page = info.value
        page.set_default_timeout(20_000)
        try:
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
    else:
        raise Fail("업무포털이 열려 있지 않습니다 — 업무포털 버튼으로 로그인하세요")
    n = stable_count(page)
    if n is None:
        raise Fail("기관접수대기 숫자를 찾지 못했습니다 (통합관리 로그인이 풀렸을 수 있습니다)")
    return {"wait": int(n)}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    if not chrome_up():
        fail("위젯 크롬이 꺼져 있습니다 — 업무포털 버튼으로 로그인하세요")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % PORT)
        try:
            v = read(browser)
        except Fail as e:
            fail(str(e))
    print("JEOPSU " + json.dumps(v), flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        fail((str(e).splitlines() or [type(e).__name__])[0][:140])
