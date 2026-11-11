# Maldonado Advogados — Central de Automações

Plataforma de automação jurídica do escritório **Maldonado Advogados**
(Dr. Renan Gomes Maldonado de Jesus — OAB/RO 5769 — Porto Velho/RO).
Nicho: dívida rural bancária.

Três frentes de automação — **Controladoria é a prioridade** deste projeto:

| Squad | O que faz | Comando-chave |
|-------|-----------|---------------|
| **Controladoria** (prioridade) | Captura intimações/publicações via DJEN, classifica providência/tese/prazo, cruza com ADVBOX, oferece criar tarefa | `python OPERACIONAL/main.py triagem --dias 7` |
| **Dívida Rural** | Produção de peça (prorrogação, descaracterização de mora, revisional) — via agente Claude, calibrado pelos 3 modelos reais do escritório | agente `.claude/agents/maldonado-divida-rural.md` |
| **Jurimetria** | "Cérebro" do escritório: prognóstico por tese/tribunal, banco de teses (vault Obsidian) | agente `.claude/agents/maldonado-jurimetria.md` |
| **Financeiro** | Situação de cada cliente (em dia / em atraso / bloqueado), régua de cobrança, histórico de negociação, ADVBOX → Asaas, saneamento e painel | `python FINANCEIRO/main.py situacao` |
| **Trava financeira** | Cliente com mais de 90 dias em atraso sai marcado na triagem e não vira tarefa de produção | automática dentro da `triagem` |
| **Marketing (Meta Ads)** | Cria a campanha de WhatsApp para produtor rural (nasce pausada) e mede gasto, conversas e custo por lead | `python MARKETING/criar_campanha.py` |
| **Laudos** | Recálculo da cédula de crédito rural (cobrado × recalculado) com minuta do laudo em .docx | `python LAUDOS/laudo_credito_rural.py caso.json` |

## Comandos do pacote financeiro, marketing e laudos

| O que | Comando |
|---|---|
| Quem está em dia, em atraso e bloqueado | `python FINANCEIRO/main.py situacao` |
| Mensagens de cobrança do dia (planilha para o WhatsApp do financeiro) | `python FINANCEIRO/main.py regua --registrar` |
| Registrar uma negociação | `python FINANCEIRO/main.py historico "NOME DO CLIENTE" -a "ligou, paga dia 20" --autor Savio` |
| Ver o histórico de um cliente | `python FINANCEIRO/main.py historico "NOME DO CLIENTE"` |
| Parcelas do ADVBOX sem cobrança no Asaas (emite com confirmação) | `python FINANCEIRO/main.py emitir --dias 30 --criar` |
| Contratos que estão num sistema e no outro não | `python FINANCEIRO/main.py saneamento` |
| Painel do financeiro no navegador | `python FINANCEIRO/main.py painel` |
| Plano da campanha (não cria nada) | `python MARKETING/criar_campanha.py` |
| Criar a campanha na conta (PAUSADA) | `python MARKETING/criar_campanha.py --criar` |
| Ligar / pausar a campanha | `python MARKETING/criar_campanha.py --ativar <id>` / `--pausar <id>` |
| Relatório do Meta (gasto, conversas, custo por lead) | `python MARKETING/relatorio_meta.py --dias 7` |
| Laudo de recálculo de cédula rural | `python LAUDOS/laudo_credito_rural.py LAUDOS/exemplo_cedula.json` |

Textos, estados e orçamento da campanha: `MARKETING/campanha_produtor_rural.json`.
Artes: `MARKETING/criativos/`. Tudo o que é gerado com dado de cliente vai para `SAIDA/`
(fora do GitHub).

## Baixar o sistema

Repositório: https://github.com/pabadvogados-hub/maldonado-advogados

```bash
git clone https://github.com/pabadvogados-hub/maldonado-advogados.git
cd maldonado-advogados
```

Sem Git instalado? Baixe o ZIP direto em **Code → Download ZIP** na página do repositório acima
e descompacte numa pasta — funciona igual, só não recebe atualizações automáticas depois.

## Instalação rápida

O escritório tem máquinas **Windows e Mac** — use o instalador do seu sistema (ambos fazem a
mesma coisa: criam o ambiente, instalam as dependências e preparam o `config/.env`):

**Windows** — dê duplo clique em `deploy\instalar_windows.bat` (ou rode no terminal):
```bat
deploy\instalar_windows.bat
```

**Mac:**
```bash
chmod +x deploy/instalar_mac.sh
./deploy/instalar_mac.sh
```

### Passo a passo manual (se preferir não usar o instalador)

**Windows (cmd/PowerShell):**
```bat
python -m venv venv
venv\Scripts\activate.bat
pip install -r requirements.txt
copy config\.env.example config\.env
```

**Mac/Linux (bash/zsh):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env
```

**Depois, nos dois sistemas:**
1. Edite `config/.env` — preencha `ADVBOX_API_TOKEN` e `DJEN_OAB_LISTA`.
2. Edite `config/equipe.py` — preencha os IDs de usuário do ADVBOX.
3. Teste (só leitura, não cria nada):
   ```
   python OPERACIONAL/main.py triagem --dias 7
   ```

> **Antes de rodar em produção, leia `docs/ONBOARDING.md`** — checklist passo a passo de
> credenciais. As automações rodam de forma segura enquanto algo não estiver configurado
> (nada é criado/alterado sem credencial e sem confirmação manual).

## Rodar a triagem todo dia sozinha (agendamento)

A leitura/classificação diária pode rodar **sozinha, sem abrir prompt** — só a criação de tarefa
no ADVBOX continua manual (regra de ouro). Agendar uma vez e esquecer:

**Windows:**
```bat
deploy\agendar_triagem_windows.bat
```

**Mac:**
```bash
chmod +x deploy/agendar_triagem_mac.sh
./deploy/agendar_triagem_mac.sh
```

Isso agenda `triagem --dias 1 --salvar` pra rodar **todo dia às 08:00**, salvando o relatório em
`logs/triagem_AAAA-MM-DD_HHMM.txt`. A Controladoria abre o relatório do dia de manhã e, pros itens
que quiser virar tarefa, roda na mão:
```
python OPERACIONAL/main.py triagem --dias 1 --criar-tarefa
```
(pede confirmação item a item — nunca cria em lote sozinho). As tarefas criadas saem no nome da
**Controladoria** (`config/equipe.py` → `USUARIOS_ADVBOX["CONTROLADORIA"]`), não do Dr. Renan.

## Estrutura
Ver `CLAUDE.md` para a árvore completa e as regras de cada squad.

## Regra de ouro
A IA **nunca protocola** e **nunca cria/move tarefa sem confirmação explícita**. Toda peça e
toda triagem terminam prontas para revisão da Dra. Juliana / do Dr. Renan.

## Segurança
- Segredos ficam **somente** em `config/.env` (nunca versionado — ver `.gitignore`).
- Nenhuma credencial vem pré-preenchida neste repositório.
