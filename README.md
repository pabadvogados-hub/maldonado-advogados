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

## Instalação rápida

```bash
# 1. Ambiente
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Configuração
copy config\.env.example config\.env   # depois edite config\.env
# preencha config\equipe.py com os IDs ADVBOX e OABs monitoradas

# 3. Teste (so leitura, nao cria nada)
python OPERACIONAL/main.py triagem --dias 7
```

> **Antes de rodar em produção, leia `docs/ONBOARDING.md`** — checklist passo a passo de
> credenciais. As automações rodam de forma segura enquanto algo não estiver configurado
> (nada é criado/alterado sem credencial e sem confirmação manual).

## Estrutura
Ver `CLAUDE.md` para a árvore completa e as regras de cada squad.

## Regra de ouro
A IA **nunca protocola** e **nunca cria/move tarefa sem confirmação explícita**. Toda peça e
toda triagem terminam prontas para revisão da Dra. Juliana / do Dr. Renan.

## Segurança
- Segredos ficam **somente** em `config/.env` (nunca versionado — ver `.gitignore`).
- Nenhuma credencial vem pré-preenchida neste repositório.
