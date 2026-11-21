# -*- coding: utf-8 -*-
"""사용설명서 만들기: guide/template.html 의 {{img:이름}} 자리에 guide/img/이름.png 를 그대로 넣어(base64)
그림까지 한 파일에 든 «배포/안내서.html» 을 만든다. 안내서를 고칠 때는 template.html 을 고치고 이 파일을 실행한다.
(안내서.html 은 설치 묶음의 «사용설명서.html» 과 위젯 ⚙ → 도움말 → 사용설명서 로 들어간다 — build.py 참고)"""
import base64
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "안내서.html"


def main():
    t = (HERE / "template.html").read_text(encoding="utf-8")

    def img(m):
        p = HERE / "img" / (m.group(1) + ".png")
        if not p.exists():
            sys.exit("X 그림이 없습니다: %s" % p.name)
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")

    html = re.sub(r"\{\{img:([A-Za-z0-9_]+)\}\}", img, t)
    if "{{" in html:
        sys.exit("X 채우지 못한 자리가 있습니다")
    OUT.write_text(html, encoding="utf-8")
    print("OK %s (%d KB)" % (OUT.name, OUT.stat().st_size // 1024))


if __name__ == "__main__":
    main()
