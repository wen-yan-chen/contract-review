# 一步提交 AgentsHub PR
# 用法：
#   .\submit_agentshub.ps1 -ForkUrl "https://gitcode.com/你的用户名/AgentsHub_xxxx.git"
param(
    [Parameter(Mandatory = $true)]
    [string]$ForkUrl,
    [string]$WorkDir = "D:\contest-32\_submit",
    [string]$SourceDir = "D:\contest-32\submission\贷款合同审查助手",
    [string]$TargetRel = "行业智能体/金融/贷款合同审查助手"
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

# ---------- 0. 前置检查 ----------
Step "检查环境"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "未找到 git，请先安装 Git for Windows"
}
if (-not (Test-Path $SourceDir)) {
    throw "找不到待提交目录：$SourceDir"
}
$files = @("agent.json", "prompt.md", "README.md")
foreach ($f in $files) {
    if (-not (Test-Path (Join-Path $SourceDir $f))) { throw "缺少文件：$f" }
}
Ok "待提交文件齐全：$($files -join ', ')"

# Fork 名称可能被系统自动加后缀（如 AgentsHub_2943），这里只要求是 gitcode 仓库地址
if ($ForkUrl -notmatch '^https://gitcode\.com/[^/]+/[^/]+?(\.git)?$') {
    throw "ForkUrl 格式不对，应形如 https://gitcode.com/用户名/仓库名.git"
}
$ForkUrl = $ForkUrl -replace '\.git$', ''
$parts = ($ForkUrl -replace '^https://gitcode\.com/', '') -split '/'
$owner = $parts[0]
$repo = $parts[1]
Ok "Fork 仓库：$owner / $repo"

# ---------- 1. 克隆或更新 ----------
Step "准备本地仓库：$WorkDir"
$hasRepo = Test-Path (Join-Path $WorkDir ".git\config")
if ($hasRepo) {
    Push-Location $WorkDir
    $remote = (git remote get-url origin 2>$null)
    if ($remote -and ($remote -notmatch [regex]::Escape($repo))) {
        Pop-Location
        Warn "本地目录是另一个仓库的克隆（$remote），将重新克隆"
        Remove-Item $WorkDir -Recurse -Force
        $hasRepo = $false
    } else {
        git fetch origin --quiet
        git checkout main --quiet 2>$null
        git reset --hard origin/main --quiet
        Pop-Location
        Ok "已更新现有克隆"
    }
}
if (-not $hasRepo) {
    if (Test-Path $WorkDir) { Remove-Item $WorkDir -Recurse -Force }
    git clone --depth 1 $ForkUrl $WorkDir
    if ($LASTEXITCODE -ne 0) { throw "克隆失败：检查 fork 地址是否正确、是否已登录 GitCode" }
    Ok "克隆完成"
}

# ---------- 2. 复制文件 ----------
Step "复制文件到 $TargetRel"
$dest = Join-Path $WorkDir $TargetRel
New-Item -ItemType Directory -Path $dest -Force | Out-Null
foreach ($f in $files) {
    Copy-Item (Join-Path $SourceDir $f) (Join-Path $dest $f) -Force
    $kb = [math]::Round((Get-Item (Join-Path $dest $f)).Length / 1KB, 1)
    Ok "$f  ($kb KB)"
}

# ---------- 3. 提交并推送 ----------
Push-Location $WorkDir
try {
    Step "提交变更"
    git add $TargetRel
    $staged = git diff --cached --name-only
    if (-not $staged) {
        Warn "没有变更需要提交（可能已经提交过）"
    } else {
        git -c core.safecrlf=false commit -q -m "feat: 新增贷款合同审查助手

- 40 条审查规则（利率/担保/违约/合规）
- 原文定位精确到字符、风险三级分级、可采纳修改建议
- 授信批复要素比对
- 完整项目见 PR 描述"
        if ($LASTEXITCODE -ne 0) { throw "提交失败" }
        Ok "已提交：$(git log --oneline -1)"
    }

    Step "推送到 fork"
    Warn "首次推送会要求输入 GitCode 用户名与密码/私人令牌"
    git push origin main
    if ($LASTEXITCODE -ne 0) {
        throw "推送失败。常见原因：未登录、无权限、或需要私人令牌（见 docs/提交PR指南.md）"
    }
    Ok "推送成功"
}
finally {
    Pop-Location
}

# ---------- 4. 下一步 ----------
Step "代码已推送，现在去建 PR"
Write-Host @"

  1) 打开你的 fork：
     $ForkUrl

  2) 页面顶部通常会出现「你的分支领先上游 N 个提交，创建 Pull Request」，
     点它；或点左侧「Pull Requests」→「新建 Pull Request」

  3) 目标仓库选择（不要选错）：
     源：  $owner/$repo   分支 main
     目标：ModelEngine/AgentsHub   分支 main

  4) 标题（必须一字不差）：
     [new agent] contract_review_agent

  5) 描述里贴上完整项目链接（GitHub 地址）

"@ -ForegroundColor White
