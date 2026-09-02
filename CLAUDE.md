# Maldonado Advogados - Central de Automações

> Escritório: **Maldonado Advogados** | Responsável: **Dr. Renan Gomes Maldonado de Jesus (OAB/RO 5769)** | Gerente Jurídico: **Dra. Juliana Ferreira Gusmão de Lara** | Foro: **Porto Velho - RO (TJRO)**
> Área: **Dívida rural bancária** (prorrogação/alongamento, descaracterização de mora — Tema 28/STJ, revisional bancária).
> **Prioridade do projeto: Squad Controladoria primeiro** (eliminar o gargalo das 2 controllers e das 200 correções de peça/mês) — Squads Dívida Rural e Jurimetria seguem em paralelo/sequência.

## Estrutura

```
MALDONADO_ADVOGADOS/
├── INTEGRACOES/          # Modulos compartilhados (todos os squads usam)
│   ├── google_integration.py   # Google Drive/Docs/Sheets
│   ├── advbox_integration.py   # API ADVBOX (clientes, processos, tarefas)
│   └── comunica_djen.py        # API DJEN/Comunica (CNJ) - captura de intimacoes por OAB
│
├── OPERACIONAL/           # Squad Controladoria (PRIORIDADE) + Squad Divida Rural
│   ├── main.py                     # Comandos: tarefas / processos / prazos / triagem / criar-tarefa
│   └── triagem_divida_rural.py     # Classificador: intimacao -> tese -> peca necessaria -> prioridade
│                                    # (geracao de minuta das pecas ainda e feita via agente Claude,
│                                    #  nao ha modulo Python de producao de peca neste repositorio)
│
├── docs/pop_controladoria/         # POP real da Controladoria (Dra. Juliana, 20/08/2026)
│   └── MAPA_MESTRE_CONTROLADORIA_JULIANA.png  # Mapa mestre: 3 estagios, POP-CJ-001 a 020
│
├── .claude/agents/        # Agentes Claude Code / Claude.ai (mesmo conteudo do Custom Instructions)
│   ├── maldonado-controladoria.md  # Squad Controladoria (triagem)
│   ├── maldonado-divida-rural.md   # Squad Divida Rural (producao de pecas)
│   └── maldonado-jurimetria.md     # Squad Jurimetria (banco de teses / prognostico)
│
├── DOCS_MODELOS/          # Timbrado + pecas-modelo do escritorio
├── BASE_CONHECIMENTO/     # Banco de teses (vault Obsidian) - ver Squad Jurimetria
├── CADASTROS/             # Fichas e dados de cliente
│
├── config/                # Configuracoes centralizadas
│   ├── .env               # (criar a partir de .env.example - NAO versionar)
│   ├── .env.example       # Template de variaveis
│   ├── equipe.py           # IDs de usuario ADVBOX por papel + OABs monitoradas no DJEN
│   └── credentials.json   # (credenciais Google - NAO versionar)
│
├── docs/                  # Documentacao (onboarding, white-label spec)
├── CLAUDE.md              # Este arquivo
└── requirements.txt
```

> **Fora do escopo nesta fase:** Squad Comercial/Intake (ZapSign/Atende Direito) e Squad Financeiro
> (fechamento/Asaas) não foram contratados por este cliente — o escritório já opera captação e
> financeiro por conta própria. Ver `docs/_WHITE_LABEL_SPEC.md` §5.

## Squad Controladoria (OPERACIONAL) — PRIORIDADE 1

Objetivo: eliminar a triagem manual das 2 controllers, que hoje só distribuem intimações
sem tratamento estratégico. Duas frentes, conforme o Dr. Renan definiu no fechamento:
(1) processos em andamento (intimações/publicações) e (2) novas ações iniciais.

**POP real do escritório:** a Dra. Juliana enviou o mapa mestre completo da Controladoria
(3 estágios — Entrada / Ciclo Operacional Contínuo / Encerramento — com ~20 POPs numerados
POP-CJ-001 a POP-CJ-020, cobrindo KPI, prazos D-5/D-3, saneamento, protocolo, PMP, encerramento
etc.). A imagem está em `docs/pop_controladoria/MAPA_MESTRE_CONTROLADORIA_JULIANA.png` e o
detalhamento textual completo está em `.claude/agents/maldonado-controladoria.md` — esse agente
é a fonte da verdade operacional, não o resumo abaixo (que cobre só a fatia já automatizada,
POP-CJ-003).

Comando:
```
python OPERACIONAL/main.py triagem --dias 7
python OPERACIONAL/main.py triagem --dias 7 --criar-tarefa   # cria a tarefa no ADVBOX (pede confirmacao)
```

Fluxo:
1. Busca as intimações/publicações dos últimos N dias via **DJEN/Comunica (CNJ)**, filtrando pelas
   OABs do escritório (`config/equipe.py` → `OABS_MONITORADAS`).
2. Para cada intimação, `triagem_divida_rural.py` classifica: tipo de ato, providência cabível,
   qual das 4 teses de dívida rural está envolvida (se for o caso), peça necessária e prioridade.
3. Cruza com o **ADVBOX** (`/lawsuits`) pelo número do processo, para trazer cliente e responsável.
4. Imprime o relatório de triagem (ou, com `--criar-tarefa`, cria a tarefa em `/posts` — sempre com
   confirmação manual antes de gravar).
5. Nunca protocola, nunca decide sozinho qual das 4 teses cabe quando for ambíguo — sinaliza e para.

Regras:
- Tarefas ADVBOX usam endpoint `/posts` (não `/tasks`).
- Campo `from` é o usuário responsável (`config/equipe.py` → `USUARIOS_ADVBOX["RESPONSAVEL"]`).
- Campo de mensagem é `"comments"` (não `"notes"`).
- **Nunca criar tarefa sem confirmação explícita** (`--criar-tarefa` ainda pede "s/N" no terminal).
- A API DJEN é instável (alterna respostas de "sistema ocupado" e falso-vazio para a mesma
  consulta) — o módulo já trata isso com retry/backoff; se mesmo assim vier vazio, o script avisa
  em vez de reportar silenciosamente "nenhuma intimação".

## Squad Dívida Rural (OPERACIONAL) — Produção de peças

As 4 ações centrais do escritório (ver `.claude/agents/maldonado-divida-rural.md` para o
detalhamento jurídico completo):
1. **Prorrogação/alongamento compulsório de crédito rural** (item 2.6.4 MCR + Súmula 298/STJ).
2. **Ação declaratória de descaracterização de mora** (Tema 28/STJ — distinção juros compostos x
   capitalização, Súmulas 539/541).
3. **Descaracterização de mora c/c falha na assistência técnica** (Justiça Federal, réu CEF/BB).
4. **Ação revisional de contrato bancário rural** (estrutura em tópicos I-IV).

A minuta é produzida pelo agente Claude (`.claude/agents/maldonado-divida-rural.md`), calibrado
pelas 3 peças-modelo reais em `DOCS_MODELOS/`. Toda peça sai **pronta para revisão** — nunca
protocolada automaticamente.

## Squad Jurimetria (BASE_CONHECIMENTO) — "Cérebro" do escritório

Ver `.claude/agents/maldonado-jurimetria.md` para a metodologia completa (8 passos): íntegra →
magistrado → perfil decisório → precedentes TJRO → probabilidade por pedido → veredito. Alimenta
um **vault Obsidian** em `BASE_CONHECIMENTO/` com notas por
tema/magistrado/caso, interligadas.

## ADVBOX API
- Base: https://app.advbox.com.br/api/v1
- Auth: Bearer token + User-Agent obrigatório
- Endpoint tarefas: /posts (GET e POST)
- Endpoint processos: /lawsuits
- Rate limit: GET 30/min | POST 500/dia

## DJEN/Comunica API (CNJ)
- Base: https://comunicaapi.pje.jus.br/api/v1/comunicacao
- Filtro principal: `numeroOab` + `ufOab` (não usar `nomeParte`, gera ruído).
- Instável: mesma consulta pode retornar "sistema ocupado" ou falso-vazio (`count:0`) mesmo
  havendo dados — o módulo trata isso com retry/backoff.

## Padrões de peça
- Toda peça sai no timbrado do escritório (`config/timbrado_modelo.docx` — cliente já forneceu
  Procuração e Contrato de Honorários com o timbrado real; falta isolar um `.docx` só com
  header/footer).
- Assinatura padrão: Dr. Renan Gomes Maldonado de Jesus - OAB/RO 5769 - Porto Velho/RO.
- Formatação calibrada pelos 3 modelos reais: justificado, citações/tabelas comparativas em
  destaque (ex.: "juros compostos" x "capitalização"), sumário em tópicos I-IV na revisional.

## Credenciais (config/.env)
Todas as credenciais ficam em `config/.env` (copiar de `config/.env.example`).
NUNCA versionar o `.env`. Ver `docs/ONBOARDING.md` para o passo a passo de configuração.

## Regra de ouro
A IA **nunca protocola** e **nunca cria/move tarefa sem confirmação explícita**. Toda peça e toda
triagem terminam prontas para revisão da Dra. Juliana / do Dr. Renan.
