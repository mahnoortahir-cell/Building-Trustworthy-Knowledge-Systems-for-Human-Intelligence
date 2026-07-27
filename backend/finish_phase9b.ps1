$ErrorActionPreference = "Stop"

$branch = git branch --show-current

git add app\models\document_conversation.py app\documents\conversation_schemas.py app\documents\conversation_service.py app\documents\conversation_search_service.py app\documents\router.py tests\documents\test_conversation_endpoints.py migrations\versions\ac959336af40_add_conversation_pinning.py ..\README.md

git diff --cached --check
if ($LASTEXITCODE -ne 0) { throw "Staged diff check failed" }

git commit -m "feat(conversations): add pinning and priority ordering"
if ($LASTEXITCODE -ne 0) { throw "Commit failed" }

git push origin $branch
if ($LASTEXITCODE -ne 0) { throw "Push failed" }

$local = git rev-parse HEAD
$remote = ((git ls-remote origin "refs/heads/$branch") -split "\s+")[0]
Write-Host "Local:  $local"
Write-Host "Remote: $remote"
if ($local -ne $remote) { throw "Remote verification failed" }

Remove-Item .\.phase9b_backup -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Phase 9B committed and pushed successfully."
