# -*- coding: utf-8 -*-
"""업무포털 메인의 «K-에듀파인 전자결재 현황 > 결재(긴급) N(M)» 숫자를 읽어 한 줄(JSON)로 찍는다. 읽기 전용.

위젯 전용 크롬(포트 9324)에 이미 열려 있는 업무포털 메인 탭을 새로고침해서 최신 숫자를 읽는다.
새 로그인·새 크롬·결재 문서 열기·클릭은 하지 않는다. 크롬이 꺼져 있거나 포털 메인 탭이 없거나 로그인이 풀려 있으면
숫자를 지어내지 않고 이유만 찍고 끝낸다 (종료 코드 1).
출력(마지막 줄): SANCTN {"wait": N, "urgent": M}
"""
import json
import re
import sys
import urllib.request

PORT = 9324
MAIN_RE = re.compile(r"eduptl\.kr/bpm_man_mn00_001\.do")
COUNT_RE = re.compile(r"^\s*(\d+)\s*\(\s*(\d+)\s*\)\s*$")

FIND_JS = r"""() => {
  const box = document.querySelector('#keduBox');
  if (!box) return null;
  for (const a of box.querySelectorAll('a')) {
    if (/sanctnWait/.test(a.getAttribute('href') || '') && /^\s*\d+\s*\(\s*\d+\s*\)\s*$/.test(a.textContent)) return a.textContent;
  }
  return null;
}"""


def fail(msg):
    print("❌  " + msg, flush=True)
    sys.exit(1)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    try:
        urllib.request.urlopen("http://127.0.0.1:%d/json/version" % PORT, timeout=3).read()
    except Exception:
        fail("위젯 크롬이 꺼져 있습니다 — 업무포털 버튼으로 로그인하세요")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % PORT)
        page = next((pg for ctx in browser.contexts for pg in ctx.pages if MAIN_RE.search(pg.url)), None)
        if page is None:
            fail("업무포털 메인 탭이 없습니다 — 업무포털 버튼으로 로그인하세요")
        page.set_default_timeout(20_000)
        try:
            page.reload(wait_until="domcontentloaded")
        except Exception:
            fail("업무포털 새로고침에 실패했습니다")
        if not MAIN_RE.search(page.url):
            fail("업무포털 로그인이 풀렸습니다 — 업무포털 버튼으로 로그인하세요")
        text = None
        for _ in range(40):                      # 최대 약 20초: 에듀파인 숫자는 화면이 뜬 뒤에 채워진다
            text = page.evaluate(FIND_JS)
            if text:
                break
            page.wait_for_timeout(500)
        if not text:
            fail("결재대기 숫자를 찾지 못했습니다 (에듀파인 연결이 안 됐을 수 있습니다)")
    m = COUNT_RE.match(text)
    print("SANCTN " + json.dumps({"wait": int(m.group(1)), "urgent": int(m.group(2))}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        fail((str(e).splitlines() or [type(e).__name__])[0][:140])
