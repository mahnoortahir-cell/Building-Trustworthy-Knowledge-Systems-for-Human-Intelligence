$ErrorActionPreference = "Stop"

python .\phase9b_patch.py
if ($LASTEXITCODE -ne 0) { throw "Patch failed" }

alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Migration failed" }

python -m compileall app\documents app\models\document_conversation.py tests\documents\test_conversation_endpoints.py
if ($LASTEXITCODE -ne 0) { throw "Compile failed" }

git diff --check
if ($LASTEXITCODE -ne 0) { throw "Diff check failed" }

pytest tests\documents\test_conversation_endpoints.py -q
if ($LASTEXITCODE -ne 0) { throw "Focused tests failed" }

pytest tests\documents -q
if ($LASTEXITCODE -ne 0) { throw "Document tests failed" }

Write-Host "`nPhase 9B checks passed. Review with: git diff"
Write-Host "Then run: .\finish_phase9b.ps1"
