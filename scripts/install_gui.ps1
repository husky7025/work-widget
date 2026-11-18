# 업무 위젯 설치 — 터미널 없이 작은 안내 창으로 진행한다 (install_widget.cmd 가 부른다)
# 실제 설치는 install_widget.ps1 이 숨은 창에서 하고, 이 창은 설치 기록을 읽어 게이지·단계·지나간 시간으로 보여 준다.
# 시험용: $env:WORK_WIDGET_FAKE_WORKER 에 다른 ps1 경로를 주면 그것을 대신 돌린다.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$here = $PSScriptRoot
$log = Join-Path $env:TEMP "업무위젯_설치기록.txt"
Remove-Item $log -ErrorAction SilentlyContinue

# 단계: 기록에 이 글자가 나오면 그 단계로 넘어간다. (시작%, 끝%, 보통 걸리는 초, 목록 번호, 설명)
$stages = @(
  @{ m = "";                          a = 0;  b = 6;  sec = 8;   row = 0; say = "설치 파일을 푸는 중이에요." },
  @{ m = "위젯 파일을 넣는";          a = 6;  b = 12; sec = 8;   row = 1; say = "위젯 파일을 넣는 중이에요." },
  @{ m = "파이썬 확인 중";            a = 12; b = 16; sec = 10;  row = 2; say = "파이썬이 있는지 확인하는 중이에요." },
  @{ m = "파이썬이 없어서";           a = 16; b = 45; sec = 240; row = 2; say = "파이썬을 설치하는 중이에요.`n처음 설치하는 PC는 몇 분 걸려요." },
  @{ m = "python.org 공식 설치";      a = 20; b = 45; sec = 180; row = 2; say = "파이썬을 설치하는 중이에요.`n처음 설치하는 PC는 몇 분 걸려요." },
  @{ m = "가상환경(.venv)";           a = 45; b = 50; sec = 20;  row = 3; say = "위젯이 쓸 공간을 만드는 중이에요." },
  @{ m = "필요한 패키지 설치";        a = 50; b = 78; sec = 120; row = 3; say = "필요한 도구를 받는 중이에요. (1~3분)" },
  @{ m = "브라우저 제어 도구";        a = 78; b = 95; sec = 120; row = 4; say = "크롬을 다루는 도구를 받는 중이에요. (1~3분)" },
  @{ m = "설치 완료!";                a = 95; b = 99; sec = 15;  row = 5; say = "설정 창을 준비하는 중이에요." }
)
$rows = @("설치 파일 풀기", "위젯 파일 넣기", "파이썬 준비", "필요한 도구 받기", "크롬 제어 도구 받기", "마무리")

$ui = New-Object Drawing.Font("Malgun Gothic", 10)
$f = New-Object Windows.Forms.Form
$f.Text = "업무 위젯 설치"; $f.ClientSize = New-Object Drawing.Size(470, 400); $f.StartPosition = "CenterScreen"
$f.FormBorderStyle = "FixedDialog"; $f.MaximizeBox = $false; $f.MinimizeBox = $true; $f.TopMost = $true
$f.BackColor = [Drawing.Color]::White; $f.Font = $ui

$t = New-Object Windows.Forms.Label; $t.Location = "22,16"; $t.Size = "430,30"
$t.Font = New-Object Drawing.Font("Malgun Gothic", 13, [Drawing.FontStyle]::Bold); $t.Text = "업무 위젯을 설치하고 있어요"

# 게이지 (직접 그림: 초록 막대 + 움직이는 빛 → 멈춰 보이지 않게)
$bar = New-Object Windows.Forms.PictureBox; $bar.Location = "22,56"; $bar.Size = "380,26"
$pct = New-Object Windows.Forms.Label; $pct.Location = "408,56"; $pct.Size = "50,26"; $pct.TextAlign = "MiddleRight"
$pct.Font = New-Object Drawing.Font("Malgun Gothic", 11, [Drawing.FontStyle]::Bold); $pct.ForeColor = [Drawing.Color]::FromArgb(22, 163, 74); $pct.Text = "0%"
$script:val = 0.0; $script:shine = 0; $script:barColor = [Drawing.Color]::FromArgb(22, 163, 74)
$script:brBack = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(229, 231, 235))
$script:penBorder = New-Object Drawing.Pen ([Drawing.Color]::FromArgb(209, 213, 219))
$script:brBar = $null; $script:brBarColor = $null
$bar.Add_Paint({
  param($sender, $e)
  $g = $e.Graphics; $g.SmoothingMode = "AntiAlias"
  $w = $sender.Width; $h = $sender.Height
  $g.FillRectangle($script:brBack, 0, 0, $w, $h)
  $fw = [int]([Math]::Round($w * $script:val / 100.0))
  if ($fw -gt 0) {
    if ($script:brBarColor -ne $script:barColor) {          # 막대 색이 바뀔 때만 새로 만든다 (GDI 핸들 누적 방지)
      if ($script:brBar) { $script:brBar.Dispose() }
      $script:brBar = New-Object Drawing.SolidBrush $script:barColor; $script:brBarColor = $script:barColor
    }
    $g.FillRectangle($script:brBar, 0, 0, $fw, $h)
    if (-not $script:done) {
      $x = ($script:shine % ($fw + 60)) - 60
      $rect = New-Object Drawing.Rectangle($x, 0, 60, $h)
      $lg = New-Object Drawing.Drawing2D.LinearGradientBrush($rect, [Drawing.Color]::FromArgb(0, 255, 255, 255), [Drawing.Color]::FromArgb(0, 255, 255, 255), 0.0)
      try {
        $cb = New-Object Drawing.Drawing2D.ColorBlend(3)
        $cb.Colors = @([Drawing.Color]::FromArgb(0, 255, 255, 255), [Drawing.Color]::FromArgb(110, 255, 255, 255), [Drawing.Color]::FromArgb(0, 255, 255, 255))
        $cb.Positions = @(0.0, 0.5, 1.0); $lg.InterpolationColors = $cb
        $g.SetClip((New-Object Drawing.Rectangle(0, 0, $fw, $h)))
        $g.FillRectangle($lg, $rect); $g.ResetClip()
      } finally { $lg.Dispose() }
    }
  }
  $g.DrawRectangle($script:penBorder, 0, 0, $w - 1, $h - 1)
})

$s = New-Object Windows.Forms.Label; $s.Location = "22,92"; $s.Size = "430,44"; $s.Text = "준비하는 중..."

# 단계 목록
$rowLabels = @()
for ($i = 0; $i -lt $rows.Count; $i++) {
  $l = New-Object Windows.Forms.Label; $l.Location = New-Object Drawing.Point(30, (144 + 28 * $i)); $l.Size = "420,26"
  $l.Text = "○  " + $rows[$i]; $l.ForeColor = [Drawing.Color]::FromArgb(156, 163, 175)
  $rowLabels += $l
}
$el = New-Object Windows.Forms.Label; $el.Location = "22,318"; $el.Size = "430,22"; $el.ForeColor = [Drawing.Color]::FromArgb(75, 85, 99)
$n = New-Object Windows.Forms.Label; $n.Location = "22,342"; $n.Size = "430,50"; $n.ForeColor = [Drawing.Color]::DimGray
$n.Text = "보통 5~15분 걸려요. 게이지가 천천히 움직여도 정상이니`n이 창을 닫지 말고 기다려 주세요."
$f.Controls.AddRange(@($t, $bar, $pct, $s, $el, $n) + $rowLabels)

$script:fontBold = New-Object Drawing.Font("Malgun Gothic", 10, [Drawing.FontStyle]::Bold)
function Set-Rows($cur, $allDone) {
  for ($i = 0; $i -lt $rowLabels.Count; $i++) {
    $l = $rowLabels[$i]
    if ($allDone -or $i -lt $cur) { $l.Text = "✔  " + $rows[$i]; $l.ForeColor = [Drawing.Color]::FromArgb(22, 163, 74); $l.Font = $ui }
    elseif ($i -eq $cur) { $l.Text = "▶  " + $rows[$i] + " ..."; $l.ForeColor = [Drawing.Color]::FromArgb(17, 24, 39); $l.Font = $script:fontBold }
    else { $l.Text = "○  " + $rows[$i]; $l.ForeColor = [Drawing.Color]::FromArgb(156, 163, 175); $l.Font = $ui }
  }
}
Set-Rows 0 $false

function Read-Log {
  if (-not (Test-Path $log)) { return "" }
  try {
    $fs = [IO.File]::Open($log, "Open", "Read", "ReadWrite")
    try { $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8); return $sr.ReadToEnd() } finally { $fs.Close() }
  } catch { return "" }
}

$worker = Join-Path $here "install_widget.ps1"
if ($env:WORK_WIDGET_FAKE_WORKER) { $worker = $env:WORK_WIDGET_FAKE_WORKER }
# 한 줄씩 바로 기록 파일에 붙인다 (Out-File 은 모아 두었다 쓰는 일이 있어 화면이 늦게 바뀐다)
$cmd = "& '$worker' *>&1 | ForEach-Object { [IO.File]::AppendAllText('$log', `$_.ToString() + [Environment]::NewLine, [Text.Encoding]::UTF8) }; exit `$LASTEXITCODE"
$p = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $cmd)

$script:done = $false
$script:start = Get-Date
$script:stage = 0
$script:stageStart = Get-Date
$script:lastRead = [DateTime]::MinValue
$script:txt = ""
$tm = New-Object Windows.Forms.Timer; $tm.Interval = 50
$tm.Add_Tick({
  $now = Get-Date
  if (($now - $script:lastRead).TotalMilliseconds -ge 700) {
    $script:lastRead = $now
    $script:txt = Read-Log
    for ($k = $stages.Count - 1; $k -gt $script:stage; $k--) {
      if ($stages[$k].m -and $script:txt.Contains($stages[$k].m)) { $script:stage = $k; $script:stageStart = $now; break }
    }
    $st = $stages[$script:stage]
    $s.Text = $st.say
    Set-Rows $st.row $false
    $sec = [int]($now - $script:start).TotalSeconds
    $el.Text = "지나간 시간  {0}분 {1:00}초" -f [Math]::Floor($sec / 60), ($sec % 60)
  }
  if (-not $script:done) {
    # 단계 안에서도 시간이 갈수록 조금씩 차오른다 (끝 칸 바로 앞까지만)
    $st = $stages[$script:stage]
    $x = ($now - $script:stageStart).TotalSeconds / $st.sec
    $target = $st.a + ($st.b - $st.a) * (1 - [Math]::Exp(-$x))
    if ($target -gt $script:val) { $script:val = [Math]::Min($target, $script:val + 1.2) }
    $script:shine += 6
    $pct.Text = "{0}%" -f [int][Math]::Floor($script:val)
    $bar.Invalidate()
  }
  if ($p.HasExited -and -not $script:done) {
    $script:txt = Read-Log
    $script:done = $true; $tm.Stop()
    if ($p.ExitCode -eq 0 -and $script:txt.Contains("[4/4] 끝났습니다")) {
      $script:val = 100; $pct.Text = "100%"; $bar.Invalidate()
      Set-Rows 0 $true
      $t.Text = "설치가 끝났어요!"; $t.ForeColor = [Drawing.Color]::FromArgb(22, 163, 74)
      $s.Text = "곧 «설정 창»이 떠요.`n지역 선택 → 인증서 암호 입력 → [저장하고 위젯 켜기]"
      $n.Text = "암호를 칠 때 글자가 안 보여도 정상이에요. 이 창은 닫아도 됩니다."
    } else {
      $script:barColor = [Drawing.Color]::FromArgb(220, 38, 38); $pct.ForeColor = $script:barColor; $bar.Invalidate()
      $t.Text = "설치가 끝나지 않았어요"; $t.ForeColor = $script:barColor
      $fr = $rowLabels[$stages[$script:stage].row]; $fr.Text = "✖  " + $rows[$stages[$script:stage].row] + " (여기서 멈췄어요)"; $fr.ForeColor = $script:barColor
      $last = ($script:txt -split "`r?`n" | Where-Object { $_ -match "X " } | Select-Object -Last 1)
      $s.Text = "아래 파일을 선생님(관리자)께 보내 주세요:`n$log"
      if ($last) { $n.Text = $last.Trim() } else { $n.Text = "학교망이 막는 경우가 있어요. 휴대폰 테더링으로 다시 눌러 보세요." }
      $n.ForeColor = [Drawing.Color]::Firebrick
    }
  }
})
$tm.Start()
$f.Add_FormClosing({ if (-not $script:done) { $r = [Windows.Forms.MessageBox]::Show("설치가 아직 끝나지 않았어요. 정말 닫을까요?", "업무 위젯 설치", "YesNo", "Question"); if ($r -ne "Yes") { $_.Cancel = $true } else { try { if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } } catch {} } } })
[void]$f.ShowDialog()
