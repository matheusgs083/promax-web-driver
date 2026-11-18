@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
rem Login na mesma unidade do Edge; Patos para testar a troca 2210003 -> 2210004.
set PROMAX_REPORT_UNIT=PATOS
echo ATENCAO: pare o mainWorker antes se este PC usar o mesmo usuario Promax (1 sessao por usuario).
echo.
echo === 1) 03114902 Liga Entrega (mes corrente) - entra em Patos (2210003) e troca para Sume (2210004), sem publicar ===
set PROMAX_HTTP_GRUPOS=liga_entrega
python cli.py relatorios --perfil liga_entrega --rotinas 03114902_BOT --unidade 2210003 --unidade 2210004 --somente-baixar
echo CODIGO_SAIDA=%ERRORLEVEL%
echo.
echo === 2) 03114902 Mensal do Fechamento da Liga (mes passado) - entra em Patos (2210003) e troca para Sume (2210004), sem publicar ===
set PROMAX_HTTP_GRUPOS=liga_entrega_fechamento
python cli.py relatorios --perfil liga_entrega_fechamento --rotinas 03114902_MENSAL_LIGA --unidade 2210003 --unidade 2210004 --somente-baixar
echo CODIGO_SAIDA=%ERRORLEVEL%
pause
