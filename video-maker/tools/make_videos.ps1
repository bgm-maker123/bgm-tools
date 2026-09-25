# ============================================================
#  ワンクリック動画メーカー 本体
#  run.bat から呼び出されます。このファイルは直接開かなくてOKです。
# ============================================================

$ErrorActionPreference = 'Stop'

# ------------------------------------------------------------
#  設定（慣れてきたら数字を変えてもOK）
# ------------------------------------------------------------
$LongDurationSec  = 3600    # 1時間動画の長さ（秒）
$LongFps          = 1       # 1時間動画のフレームレート（静止画なので1で十分。軽くて速い）
$LongCrf          = 20      # 画質（小さいほど高画質・重い。18〜23くらいが目安）
$LongFadeOutSec   = 3       # 1時間動画の最後の音声フェードアウト（秒）

$ShortDurationSec = 33      # ショート動画の長さ（秒）
$ShortFps         = 25      # ショート動画のフレームレート
$ShortZoomEnd     = 1.15    # ズームの最終倍率（1.0 → この倍率まで）
$ShortFadeOutSec  = 3       # ショート動画の最後の音声フェードアウト（秒）
$ShortCrf         = 20      # ショート動画の画質

$AudioBitrate     = '192k'  # 音声の音質

# タイトル文字のフォント（上から順に探して、最初に見つかったものを使います）
$FontCandidates = @(
    'YuGothB.ttc',        # 游ゴシック Bold
    'meiryob.ttc',        # メイリオ Bold
    'BIZ-UDGothicB.ttc',  # BIZ UDゴシック Bold
    'meiryo.ttc',         # メイリオ
    'msgothic.ttc'        # MS ゴシック
)

# ------------------------------------------------------------
#  ここから下はプログラム本体です
# ------------------------------------------------------------
$Root      = Split-Path -Parent $PSScriptRoot
$InputDir  = Join-Path $Root 'input'
$OutputDir = Join-Path $Root 'output'
$WorkDir   = Join-Path $PSScriptRoot '.work'
$Inv       = [System.Globalization.CultureInfo]::InvariantCulture

function Say([string]$msg, [string]$color = 'Gray') { Write-Host $msg -ForegroundColor $color }
function Fail([string]$msg) {
    Write-Host ''
    Write-Host "【エラー】$msg" -ForegroundColor Red
    Write-Host ''
    exit 1
}
function Num([double]$v) { return $v.ToString('0.#####', $Inv) }

# 全角の数字やコロンを半角にする
function To-Hankaku([string]$s) {
    $zen = '０１２３４５６７８９：．'
    $han = '0123456789:.'
    $sb = New-Object System.Text.StringBuilder
    foreach ($ch in $s.ToCharArray()) {
        $i = $zen.IndexOf($ch)
        if ($i -ge 0) { [void]$sb.Append($han[$i]) } else { [void]$sb.Append($ch) }
    }
    return $sb.ToString().Trim()
}

# 「83」「1:23」「0:01:23」を秒に変換。変換できなければ $null
function Parse-Time([string]$text) {
    $t = To-Hankaku $text
    if ($t -eq '') { return 0.0 }
    if ($t -notmatch '^\d+(\.\d+)?$|^\d+:\d{1,2}(\.\d+)?$|^\d+:\d{1,2}:\d{1,2}(\.\d+)?$') { return $null }
    $sec = 0.0
    foreach ($part in $t.Split(':')) { $sec = $sec * 60 + [double]::Parse($part, $Inv) }
    return $sec
}

function Format-Time([double]$sec) {
    $m = [math]::Floor($sec / 60)
    $s = $sec - $m * 60
    return ('{0}:{1}' -f $m, $s.ToString('00.##', $Inv))
}

# 文字の見た目の幅（全角=1、半角=0.55 くらいとして計算）
function Visual-Width([string]$s) {
    $w = 0.0
    foreach ($ch in $s.ToCharArray()) {
        if ([int]$ch -lt 0x2E80 -or ([int]$ch -ge 0xFF61 -and [int]$ch -le 0xFF9F)) { $w += 0.55 } else { $w += 1.0 }
    }
    return $w
}

# ffmpeg を探す（インストール直後でも見つかるよう PATH を読み直す）
function Find-Tool([string]$name) {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
    $local = @(
        (Join-Path $Root "$name.exe"),
        (Join-Path $Root "ffmpeg\bin\$name.exe"),
        (Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links\$name.exe")
    )
    foreach ($p in $local) { if (Test-Path $p) { return $p } }
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

# ------------------------------------------------------------
Say ''
Say '========================================' Cyan
Say '   ワンクリック動画メーカー' Cyan
Say '========================================' Cyan
Say ''

# 1. ffmpeg の確認 -------------------------------------------
$ffmpeg  = Find-Tool 'ffmpeg'
$ffprobe = Find-Tool 'ffprobe'
if (-not $ffmpeg) {
    Say '【ffmpeg（動画を作るソフト）が見つかりません】' Yellow
    Say ''
    Say '最初の1回だけ、次の手順でインストールしてください。'
    Say ''
    Say '  1. スタートボタンを右クリック →「ターミナル」を開く'
    Say '  2. 下の1行をコピーして貼り付け、Enter を押す'
    Say ''
    Say '     winget install --id Gyan.FFmpeg -e' Green
    Say ''
    Say '  3. 終わったら、ターミナルとこの画面を閉じる'
    Say '  4. もう一度 run.bat をダブルクリック'
    Say ''
    exit 1
}

# 2. 曲と画像を探す ----------------------------------------
if (-not (Test-Path $InputDir))  { New-Item -ItemType Directory $InputDir | Out-Null }
if (-not (Test-Path $OutputDir)) { New-Item -ItemType Directory $OutputDir | Out-Null }

$songs  = @(Get-ChildItem -LiteralPath $InputDir -File | Where-Object { $_.Extension -match '^\.(mp3|wav|m4a|flac)$' } | Sort-Object Name)
$images = @(Get-ChildItem -LiteralPath $InputDir -File | Where-Object { $_.Extension -match '^\.(jpg|jpeg|png)$' } | Sort-Object Name)

if ($songs.Count -eq 0)  { Fail '「input」フォルダに曲（mp3）が入っていません。曲を入れてからもう一度 run.bat を実行してください。' }
if ($images.Count -eq 0) { Fail '「input」フォルダに画像（jpg / png）が入っていません。画像を入れてからもう一度 run.bat を実行してください。' }

$song = $songs[0]
# ファイル名に short（またはショート）が入った画像があれば、ショート動画にはそれを使う
$shortImg = $images | Where-Object { $_.BaseName -match '(?i)short|ショート' } | Select-Object -First 1
$longImg  = $images | Where-Object { $_.BaseName -notmatch '(?i)short|ショート' } | Select-Object -First 1
if (-not $longImg)  { $longImg = $images[0] }
if (-not $shortImg) { $shortImg = $longImg }

Say "曲      : $($song.Name)"
Say "画像    : $($longImg.Name)"
if ($shortImg.FullName -ne $longImg.FullName) { Say "ショート用画像: $($shortImg.Name)" }
if ($songs.Count -gt 1)  { Say "※ 曲が $($songs.Count) 個あります。名前順で最初の「$($song.Name)」を使います。" Yellow }
if ($images.Count -gt 2) { Say "※ 画像が $($images.Count) 個あります。名前順で最初のものを使います。" Yellow }

# 曲の長さ（分かれば表示）
$songLen = $null
if ($ffprobe) {
    $out = $null
    try { $out = & $ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 $song.FullName 2>$null } catch { }
    $d = 0.0
    if ($out -and [double]::TryParse(($out | Select-Object -First 1), [System.Globalization.NumberStyles]::Float, $Inv, [ref]$d)) {
        $songLen = $d
        Say "曲の長さ: $(Format-Time $songLen)"
    }
}
Say ''

# 3. タイトルと開始位置を入力 --------------------------------
$defaultTitle = $song.BaseName
Say 'ショート動画の上に表示するタイトルを入力してください。' Cyan
Say '  ・何も入力せず Enter → 曲のファイル名を使います'
Say '  ・「|」を入れるとそこで改行します（例: オーロラの夜空|癒しのピアノ）'
$title = Read-Host "タイトル [初期値: $defaultTitle]"
if ([string]::IsNullOrWhiteSpace($title)) { $title = $defaultTitle }
Say ''

Say 'ショート動画で使う「曲の開始位置」を入力してください。' Cyan
Say '  ・一番盛り上がる部分の少し前がおすすめです'
Say '  ・書き方の例: 1:23（1分23秒）/ 83（83秒）'
Say '  ・何も入力せず Enter → 曲の最初から'
while ($true) {
    $startText = Read-Host '開始位置 [初期値: 0:00]'
    $start = Parse-Time $startText
    if ($null -eq $start) { Say '  → 書き方が違うようです。「1:23」や「83」のように入力してください。' Yellow; continue }
    if ($songLen -and $start -ge $songLen) { Say "  → 曲の長さ（$(Format-Time $songLen)）より後ろになっています。もう一度入力してください。" Yellow; continue }
    break
}
if ($songLen -and ($start + $ShortDurationSec) -gt $songLen) {
    Say "  ※ 開始位置から曲の最後まで $ShortDurationSec 秒ないため、足りない分は曲の最初に戻って続きます。" Yellow
}
Say ''

# 4. 準備 ----------------------------------------------------
$fontFile = $null
foreach ($f in $FontCandidates) {
    $p = Join-Path $env:WINDIR "Fonts\$f"
    if (Test-Path $p) { $fontFile = $p; break }
}
if (-not $fontFile) { Fail 'タイトル用の日本語フォントが見つかりませんでした（C:\Windows\Fonts）。' }
# ffmpeg の書き方に合わせる（C:\Windows\Fonts\x.ttc → C\:/Windows/Fonts/x.ttc）
$fontEsc = $fontFile.Replace('\', '/').Replace(':', '\:')

if (Test-Path $WorkDir) { Remove-Item -LiteralPath $WorkDir -Recurse -Force }
New-Item -ItemType Directory $WorkDir | Out-Null

# タイトルを行に分けて、1行ずつテキストファイルに保存（記号も安全に表示できるように）
$lines = @($title -split '[|｜]' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' } | Select-Object -First 3)
if ($lines.Count -eq 0) { $lines = @($defaultTitle) }
$maxW = ($lines | ForEach-Object { Visual-Width $_ } | Measure-Object -Maximum).Maximum
$fontSize = [int][math]::Floor([math]::Min(96, 960 / [math]::Max($maxW, 1)))
if ($fontSize -lt 40) { $fontSize = 40 }
$lineH  = [int]($fontSize * 1.3)
$border = [int][math]::Max(4, $fontSize / 14)
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

$drawText = ''
for ($i = 0; $i -lt $lines.Count; $i++) {
    $fileName = "title$i.txt"
    [System.IO.File]::WriteAllText((Join-Path $WorkDir $fileName), $lines[$i], $utf8NoBom)
    $y = 250 + $i * $lineH
    $drawText += ",drawtext=fontfile='$fontEsc':textfile='$fileName':expansion=none" +
                 ":fontsize=$($fontSize):fontcolor=white:borderw=$($border):bordercolor=black@0.85" +
                 ":shadowx=4:shadowy=4:shadowcolor=black@0.5:x=(w-text_w)/2:y=$y"
}

$stamp    = Get-Date -Format 'yyyyMMdd_HHmm'
$baseName = $song.BaseName
$shortOut = Join-Path $OutputDir "${stamp}_${baseName}_short.mp4"
$longOut  = Join-Path $OutputDir "${stamp}_${baseName}_1hour.mp4"

# 5. ショート動画 --------------------------------------------
# 画像を 1.15 倍の大きさで縦長に切り抜き → 毎フレーム少しずつ拡大して中央を切り抜く（なめらかなズーム）
$zw = [int][math]::Ceiling(1080 * $ShortZoomEnd / 2) * 2
$zh = [int][math]::Ceiling(1920 * $ShortZoomEnd / 2) * 2
$zoomAdd = Num ($ShortZoomEnd - 1)
$fadeSt  = Num ($ShortDurationSec - $ShortFadeOutSec)
$shortFilter =
    "[0:v]scale=$($zw):$($zh):force_original_aspect_ratio=increase:flags=lanczos,crop=$($zw):$($zh),setsar=1," +
    "scale=w='trunc(1080*(1+$zoomAdd*t/$ShortDurationSec)/2)*2':h=-2:eval=frame:flags=bicubic," +
    "crop=1080:1920$drawText,format=yuv420p[v];" +
    "[1:a]afade=t=out:st=$($fadeSt):d=$ShortFadeOutSec[a]"

Say '----------------------------------------' Cyan
Say '[1/2] ショート動画を作っています…（数分かかります）' Cyan
Push-Location $WorkDir
try {
    & $ffmpeg -hide_banner -loglevel error -stats -y `
        -loop 1 -framerate $ShortFps -i $shortImg.FullName `
        -ss (Num $start) -stream_loop -1 -i $song.FullName `
        -filter_complex $shortFilter -map '[v]' -map '[a]' `
        -t $ShortDurationSec -r $ShortFps `
        -c:v libx264 -preset medium -crf $ShortCrf `
        -c:a aac -b:a $AudioBitrate -movflags +faststart `
        $shortOut
    $code = $LASTEXITCODE
} finally { Pop-Location }
if ($code -ne 0) { Fail 'ショート動画の作成に失敗しました。上に表示された英語のメッセージを確認してください。' }
Say "  → できました: $shortOut" Green
Say ''

# 6. 1時間動画 -----------------------------------------------
# 静止画向け設定: 低フレームレート + -tune stillimage で、軽く・速く書き出します
$longFadeSt = Num ($LongDurationSec - $LongFadeOutSec)
$longFilter =
    "[0:v]scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,crop=1920:1080,setsar=1,format=yuv420p[v];" +
    "[1:a]afade=t=out:st=$($longFadeSt):d=$LongFadeOutSec[a]"

Say '[2/2] 1時間動画を作っています…（数分かかります。time= が 01:00:00 になれば完了です）' Cyan
& $ffmpeg -hide_banner -loglevel error -stats -y `
    -loop 1 -framerate $LongFps -i $longImg.FullName `
    -stream_loop -1 -i $song.FullName `
    -filter_complex $longFilter -map '[v]' -map '[a]' `
    -t $LongDurationSec -r $LongFps `
    -c:v libx264 -preset veryfast -tune stillimage -crf $LongCrf -g ($LongFps * 60) `
    -c:a aac -b:a $AudioBitrate -movflags +faststart `
    $longOut
if ($LASTEXITCODE -ne 0) { Fail '1時間動画の作成に失敗しました。上に表示された英語のメッセージを確認してください。' }
Say "  → できました: $longOut" Green

Remove-Item -LiteralPath $WorkDir -Recurse -Force -ErrorAction SilentlyContinue

Say ''
Say '========================================' Green
Say '  完成しました！「output」フォルダを開きます。' Green
Say '========================================' Green
try { Start-Process explorer.exe $OutputDir } catch { }
exit 0
