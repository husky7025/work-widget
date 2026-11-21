# 업무위젯

학교 업무용 바탕화면 위젯입니다. 업무포털·나이스(복무)·에듀파인(내부기안·품의 등) 화면을 열어 주고, 에듀파인 결재대기와 교육행정데이터통합관리 기관접수대기 건수를 보여 줍니다. 공개된 [나이스 자동화 키트](https://github.com/workcalmkite-hue/neis-automation-kit)(MIT) 위에서 동작합니다.

## 선생님용 설치

1. [work-widget-setup.zip](https://github.com/husky7025/work-widget/releases/latest/download/work-widget-setup.zip) 을 받습니다.
2. 마우스 오른쪽 → **모두 풀기** → 풀린 폴더의 `install_widget.cmd` 를 더블클릭합니다.
3. 자세한 내용은 묶음 안의 `사용설명서.html` 을 보세요.

설치한 뒤에는 위젯이 하루 한 번 오전 10시에 새 버전을 확인해 **알아서 업데이트**합니다.

## 보안

- 인증서 암호는 각 PC의 Windows 자격 증명 관리자에만 저장되고, 어떤 서버로도 보내지 않습니다.
- 업데이트(`manifest.json`)는 Ed25519 로 서명돼 있습니다. 위젯은 `signing_public_key.txt` 의 공개 열쇠로 서명을 확인하고, 맞지 않으면 설치하지 않습니다. 비밀 열쇠는 이 저장소에 없습니다.
- 위젯은 화면을 열고 숫자를 읽기만 합니다. 신청·저장·결재·접수는 하지 않습니다.

## 만드는 사람용

```
build.cmd                 묶음만 만들기
build.cmd --publish       VERSION 을 올린 뒤, 커밋·push 하고 실행 → 서명된 릴리스 올리기
build.cmd --export-key D:\  서명 비밀 열쇠 백업 (잃어버리면 업데이트를 올릴 수 없음)
```
