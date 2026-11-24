# -*- coding: utf-8 -*-
"""결재대기(check_sanctn)와 기관접수대기(check_jeopsu)를 한 번에 읽는다. 읽기 전용.

30분마다 위젯이 부른다. 예전엔 둘을 따로 실행해 파이썬·Playwright 가 두 번 떴는데,
이제 위젯 크롬(포트 9324)에 한 번만 연결해 차례로 읽는다. 한쪽을 못 읽어도 다른 쪽은 읽는다.
출력: 읽은 것은  SANCTN {"wait": N, "urgent": M}  /  JEOPSU {"wait": N}
      못 읽은 것은  ❌SANCTN 이유  /  ❌JEOPSU 이유
"""
import json
import sys

import check_jeopsu
import check_sanctn


def say_fail(tag, msg):
    print("❌%s %s" % (tag, msg), flush=True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass
    if not check_sanctn.chrome_up():
        msg = "위젯 크롬이 꺼져 있습니다 — 업무포털 버튼으로 로그인하세요"
        say_fail("SANCTN", msg)
        say_fail("JEOPSU", msg)
        return
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:%d" % check_sanctn.PORT)
        for tag, mod in (("SANCTN", check_sanctn), ("JEOPSU", check_jeopsu)):
            try:
                print("%s %s" % (tag, json.dumps(mod.read(browser))), flush=True)
            except mod.Fail as e:
                say_fail(tag, str(e))
            except Exception as e:
                say_fail(tag, (str(e).splitlines() or [type(e).__name__])[0][:140])


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        say_fail("SANCTN", msg)
        say_fail("JEOPSU", msg)
