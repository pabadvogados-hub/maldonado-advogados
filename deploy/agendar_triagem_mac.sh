#!/bin/bash
# =============================================================================
#  Agenda a triagem diaria (Squad Controladoria) - macOS (launchd)
#
#  Cria um agente do launchd que roda TODO DIA as 08:00:
#      python OPERACIONAL/main.py triagem --dias 1 --salvar
#
#  IMPORTANTE: roda SEM --criar-tarefa de proposito. So LE o DJEN, cruza com
#  o ADVBOX e SALVA o relatorio em logs/ - nao cria nem altera nada sozinha.
#  Criar tarefa no ADVBOX continua sendo decisao manual da Controladoria:
#  abrir o relatorio do dia (logs/) e, se quiser, rodar
#  "python OPERACIONAL/main.py triagem --dias 1 --criar-tarefa" na mao,
#  item a item com confirmacao. Isso e proposital (regra de ouro: nunca
#  criar tarefa sem autorizacao explicita).
#
#  Rodar: chmod +x deploy/agendar_triagem_mac.sh && ./deploy/agendar_triagem_mac.sh
# =============================================================================
set -e
cd "$(dirname "$0")/.."
PASTA="$(pwd)"
PLIST="$HOME/Library/LaunchAgents/com.maldonadoadvogados.triagem.plist"

if [ ! -d "venv" ]; then
    echo "ERRO: venv nao encontrado. Rode deploy/instalar_mac.sh primeiro."
    exit 1
fi

mkdir -p "$PASTA/logs"

cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.maldonadoadvogados.triagem</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PASTA}/venv/bin/python</string>
        <string>${PASTA}/OPERACIONAL/main.py</string>
        <string>triagem</string>
        <string>--dias</string>
        <string>1</string>
        <string>--salvar</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PASTA}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${PASTA}/logs/triagem_launchd.log</string>
    <key>StandardErrorPath</key>
    <string>${PASTA}/logs/triagem_launchd_erro.log</string>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo
echo "==============================================="
echo "  Agendado! Roda todo dia as 08:00."
echo "==============================================="
echo
echo "Pra rodar uma vez agora, so pra testar:"
echo "  launchctl start com.maldonadoadvogados.triagem"
echo
echo "Pra remover o agendamento:"
echo "  launchctl unload $PLIST && rm $PLIST"
echo
echo "Os relatorios ficam salvos em: ${PASTA}/logs/"
