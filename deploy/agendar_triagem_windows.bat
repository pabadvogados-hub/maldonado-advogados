@echo off
REM =============================================================================
REM  Agenda a triagem diaria (Squad Controladoria) - WINDOWS (Task Scheduler)
REM
REM  Cria uma tarefa agendada que roda TODO DIA as 08:00 (horario da maquina):
REM      python OPERACIONAL\main.py triagem --dias 1 --salvar
REM
REM  IMPORTANTE: a tarefa agendada roda SEM --criar-tarefa de proposito.
REM  Ela so LE o DJEN, cruza com o ADVBOX e SALVA o relatorio em logs\ -
REM  nao cria nem altera nada sozinha. Criar tarefa no ADVBOX continua sendo
REM  decisao manual da Controladoria: abrir o relatorio do dia (logs\) e, se
REM  quiser, rodar "python OPERACIONAL\main.py triagem --dias 1 --criar-tarefa"
REM  na mao, item a item com confirmacao. Isso e proposital (regra de ouro:
REM  nunca criar tarefa sem autorizacao explicita).
REM
REM  Rodar este arquivo de dentro da pasta MALDONADO_ADVOGADOS.
REM =============================================================================

cd /d "%~dp0\.."
set PASTA=%cd%

if not exist venv (
    echo ERRO: venv nao encontrado. Rode deploy\instalar_windows.bat primeiro.
    pause
    exit /b 1
)

echo Criando tarefa agendada "MaldonadoTriagemDiaria" (todo dia as 08:00)...

schtasks /create /tn "MaldonadoTriagemDiaria" /tr "\"%PASTA%\venv\Scripts\python.exe\" \"%PASTA%\OPERACIONAL\main.py\" triagem --dias 1 --salvar" /sc daily /st 08:00 /f

if errorlevel 1 (
    echo.
    echo Falhou. Tente rodar este arquivo como Administrador ^(botao direito ^> Executar como administrador^).
    pause
    exit /b 1
)

echo.
echo ===============================================
echo   Agendado! Roda todo dia as 08:00.
echo ===============================================
echo.
echo Pra ver a tarefa: abra o "Agendador de Tarefas" do Windows e procure
echo "MaldonadoTriagemDiaria".
echo.
echo Pra rodar uma vez agora, so pra testar:
echo   schtasks /run /tn "MaldonadoTriagemDiaria"
echo.
echo Pra remover o agendamento:
echo   schtasks /delete /tn "MaldonadoTriagemDiaria" /f
echo.
echo Os relatorios ficam salvos em: %PASTA%\logs\
echo.
pause
