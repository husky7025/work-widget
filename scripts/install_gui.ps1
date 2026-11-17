# 업무 위젯 설치 — 터미널 없이 작은 안내 창으로 진행한다 (install_widget.cmd 가 부른다)
# 실제 설치는 install_widget.ps1 이 숨은 창에서 하고, 이 창은 진행 상황만 쉬운 말로 보여 준다.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$here = $PSScriptRoot
$log = Join-Path $env:TEMP "업무위젯_설치기록.txt"
Remove-Item $log -ErrorAction SilentlyContinue

$f = New-Object Windows.Forms.Form
$f.Text = "업무 위젯 설치"; $f.Size = New-Object Drawing.Size(460,230); $f.StartPosition = "CenterScreen"
$f.FormBorderStyle = "FixedDialog"; $f.MaximizeBox = $false; $f.MinimizeBox = $true; $f.TopMost = $true
$f.Font = New-Object Drawing.Font("Malgun Gothic",10)
$t = New-Object Windows.Forms.Label; $t.Location = "20,15"; $t.Size = "410,28"; $t.Font = New-Object Drawing.Font("Malgun Gothic",12,[Drawing.FontStyle]::Bold); $t.Text = "업무 위젯을 설치하고 있어요"
$s = New-Object Windows.Forms.Label; $s.Location = "20,55"; $s.Size = "410,50"; $s.Text = "준비하는 중..."
$b = New-Object Windows.Forms.ProgressBar; $b.Location = "20,110"; $b.Size = "405,22"; $b.Style = "Marquee"; $b.MarqueeAnimationSpeed = 30
$n = New-Object Windows.Forms.Label; $n.Location = "20,145"; $n.Size = "410,40"; $n.ForeColor = "DimGray"
$n.Text = "5~15분 걸려요. 멈춘 것처럼 보여도 정상이니 이 창을 닫지 말고 기다려 주세요."
$f.Controls.AddRange(@($t,$s,$b,$n))

$worker = Join-Path $here "install_widget.ps1"
$p = Start-Process powershell -WindowStyle Hidden -PassThru -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-Command","& '$worker' *>&1 | Out-File -Encoding utf8 '$log'; exit `$LASTEXITCODE")
$done = $false
$tm = New-Object Windows.Forms.Timer; $tm.Interval = 1500
$tm.Add_Tick({
  $txt = ""; if (Test-Path $log) { try { $txt = Get-Content $log -Raw -ErrorAction Stop } catch {} }
  if ($txt -match "\[3/4\]") { $s.Text = "필요한 프로그램을 설치하는 중이에요.`n(파이썬·도구 설치는 가장 오래 걸려요)" }
  elseif ($txt -match "\[2/4\]") { $s.Text = "위젯 파일을 넣는 중이에요." }
  elseif ($txt -match "\[1/4\]") { $s.Text = "설치 파일을 푸는 중이에요." }
  if ($p.HasExited -and -not $script:done) {
    $script:done = $true; $tm.Stop(); $b.Style = "Continuous"
    if ($p.ExitCode -eq 0 -and $txt -match "\[4/4\]") {
      $b.Value = 100; $t.Text = "설치가 끝났어요!"
      $s.Text = "곧 «설정 창»이 떠요.`n지역 선택 → 인증서 암호 입력 → [저장하고 위젯 켜기]"
      $n.Text = "암호를 칠 때 글자가 안 보여도 정상이에요. 이 창은 닫아도 됩니다."
    } else {
      $t.Text = "설치가 끝나지 않았어요"; $b.Value = 0
      $last = ($txt -split "`r?`n" | Where-Object { $_ -match "X " } | Select-Object -Last 1)
      $s.Text = "아래 파일을 선생님(관리자)께 보내 주세요:`n$log"
      if ($last) { $n.Text = $last.Trim() } else { $n.Text = "학교망이 막는 경우가 있어요. 휴대폰 테더링으로 다시 눌러 보세요." }
      $n.ForeColor = "Firebrick"
    }
  }
})
$tm.Start()
$f.Add_FormClosing({ if (-not $script:done) { $r = [Windows.Forms.MessageBox]::Show("설치가 아직 끝나지 않았어요. 정말 닫을까요?","업무 위젯 설치","YesNo","Question"); if ($r -ne "Yes") { $_.Cancel = $true } } })
[void]$f.ShowDialog()
