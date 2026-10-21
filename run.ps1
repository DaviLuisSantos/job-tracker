$env:PYTHONIOENCODING = "utf-8"
# Roda a partir da pasta do projeto — o Agendador de Tarefas inicia em outro diretório
Set-Location $PSScriptRoot
.\.venv\Scripts\python.exe main.py @args
exit $LASTEXITCODE
