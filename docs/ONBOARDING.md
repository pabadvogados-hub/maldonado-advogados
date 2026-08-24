# Onboarding — Maldonado Advogados

Checklist para colocar o sistema rodando. A prioridade é o **Squad Controladoria**
(comando `triagem`) — é o que resolve o gargalo das 2 controllers mais rápido.

## 1. Instalar dependências

```
cd MALDONADO_ADVOGADOS
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## 2. Configurar `config/.env`

```
copy config\.env.example config\.env
```

Preencher, nesta ordem de prioridade:

| Variável | Onde conseguir | Prioridade |
|---|---|---|
| `ADVBOX_API_TOKEN` | Painel ADVBOX do escritório → Configurações → API | **Crítica** — sem isso nada funciona (nem `tarefas`, nem `triagem`, nem `processos`) |
| `DJEN_OAB_LISTA` | OABs dos advogados do escritório, formato `NUMERO-UF` separado por vírgula (ex.: `5769-RO,13021-RO`) | **Crítica para o Squad Controladoria** — sem isso o comando `triagem` não busca nada |
| `GOOGLE_APPLICATION_CREDENTIALS` / `GOOGLE_OAUTH_CREDENTIALS` | Google Cloud Console (criar projeto + habilitar Drive/Docs/Calendar API) ou pedir ajuda à equipe de implantação para gerar | Necessária a partir do Squad Jurimetria (vault Obsidian no Drive) e para eventos de prazo na Agenda |
| `ANTHROPIC_API_KEY` | console.anthropic.com (conta do escritório) | Necessária se quiser rodar os agentes via API em vez de só Claude.ai/Claude Code |

## 3. Configurar `config/equipe.py`

Preencher `USUARIOS_ADVBOX` com os IDs reais (painel ADVBOX → Usuários → clicar no usuário → ID
aparece na URL) e `OABS_MONITORADAS` com as OABs a acompanhar no DJEN.

## 4. Testar a conexão com o ADVBOX

```
python -c "import sys; sys.path.insert(0,'INTEGRACOES'); from dotenv import load_dotenv; load_dotenv('config/.env'); import advbox_integration as a; print(a.testar_conexao())"
```

## 5. Rodar a primeira triagem (modo leitura, sem criar nada)

```
python OPERACIONAL/main.py triagem --dias 7
```

Isso já mostra o relatório de triagem das intimações da última semana, cruzadas com o ADVBOX —
**sem criar nem alterar nada**. Só depois de conferir que o relatório faz sentido, usar
`--criar-tarefa` (que ainda pede confirmação item a item).

## 6. Timbrado isolado

Subir em `DOCS_MODELOS/timbrado_modelo.docx` um arquivo com **apenas o cabeçalho e rodapé**
oficiais (logo, endereço, telefones, OAB) — sem conteúdo de peça. Hoje o timbrado real só existe
embutido na Procuração e no Contrato de Honorários que a Dra. Juliana já enviou; falta isolar.

## 7. Banco de teses (Squad Jurimetria)

Criar a pasta `BASE_CONHECIMENTO/` como vault Obsidian (ver estrutura sugerida em
`.claude/agents/maldonado-jurimetria.md`). Pode ser local (sincronizada por Drive/OneDrive) ou
direto numa pasta do Drive do escritório.

## 8. Instalar os agentes no Claude.ai (opcional, complementar ao Claude Code)

Ver `.claude/agents/` — os 3 arquivos (`maldonado-controladoria.md`, `maldonado-divida-rural.md`,
`maldonado-jurimetria.md`) também funcionam como Custom Instructions de Projects no Claude.ai.
Passo a passo completo em `docs/GUIA_INSTALACAO_CLAUDE_AI.md`.

## Pendências conhecidas (não bloqueiam o começo, mas faltam para o sistema completo)

- [ ] `DOCS_MODELOS/timbrado_modelo.docx` isolado.
- [ ] Credenciais reais: `ADVBOX_API_TOKEN`, `DJEN_OAB_LISTA`, Google.
- [ ] IDs em `config/equipe.py`.
- [ ] Definir onde fica o vault Obsidian (local vs. Drive).
- [ ] Confirmar com o escritório se querem geração de peça DOCX automática (via
      `google_integration.preencher_documento`, precisa de template com placeholders `{{CHAVE}}`)
      ou se preferem que a peça saia direto do chat do Claude (copiar/colar) por enquanto.
