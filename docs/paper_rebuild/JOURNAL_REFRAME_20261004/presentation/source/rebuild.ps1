# Rebuild the presentation in a private NTFS workspace.
# Requires the exact supplied template, the repository, bundled artifact-tool,
# and the already verified scientific PNG assets. No solver or evaluator is called.
param(
  [string]$WorkDir='C:\Users\ykw\.codex\tmp\legsa_paper_deck_20261004',
  [string]$Repo='\\wsl.localhost\Ubuntu-22.04\home\kaiwen\research\LegSA-GINS-WORKTREES\audit-code-xbpg-20261001',
  [string]$Template='C:\Users\ykw\Desktop\泛源定位与组合导航\组会模版.pptx'
)
$ErrorActionPreference='Stop'
$runtime=Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies'
$python=Join-Path $runtime 'python\python.exe'
$node=Join-Path $runtime 'node\bin\node.exe'
$env:LEGSA_PPT_WORKDIR=$WorkDir
$env:LEGSA_REPO=$Repo
$env:LEGSA_PPT_TEMPLATE=$Template
$env:RUNTIME_NODE_MODULES=Join-Path $runtime 'node\node_modules'
$build=Join-Path $WorkDir '.build'
New-Item -ItemType Directory -Force -Path $build | Out-Null
Get-ChildItem -LiteralPath $PSScriptRoot -File | Where-Object { $_.Extension -in '.mjs','.py' } | Copy-Item -Destination $build -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'equations') -Destination $build -Recurse -Force
if (-not (Test-Path -LiteralPath (Join-Path $build 'node_modules'))) {
  New-Item -ItemType Junction -Path (Join-Path $build 'node_modules') -Target $env:RUNTIME_NODE_MODULES | Out-Null
}
& $python (Join-Path $build 'prepare_template.py')
if ($LASTEXITCODE -ne 0) { throw 'Template preparation failed.' }
& $node (Join-Path $build 'build_final.mjs')
if ($LASTEXITCODE -ne 0) { throw 'Presentation build or finalization failed.' }
& $node (Join-Path $build 'render_finalized.mjs')
if ($LASTEXITCODE -ne 0) { throw 'Final-file render failed.' }
