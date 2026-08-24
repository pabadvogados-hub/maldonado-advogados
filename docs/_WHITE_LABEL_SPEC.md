# White-Label Spec — Maldonado Advogados

> Documento-guia interno. Toda réplica de código/documentação deve seguir este mapa.
> Objetivo: replicar as automações-base SEM nenhuma referência ao escritório de origem.
> Regra de ouro: **zero menção a "PAB", "Pamella", "São Bernardo", "Casal da IA", "CLAUD.IA"
> ou qualquer pessoa/cliente do escritório de origem (Weverton, Gi, Tom, Aneiry, Aldenor,
> Luciano, Romax, PVD, etc.).**

## 1. Identidade do escritório

| Campo | Valor Maldonado |
|-------|--------------|
| Nome do escritório | Maldonado Advogados |
| Razão social judicial | RENAN MALDONADO SOCIEDADE INDIVIDUAL DE ADVOCACIA — CNPJ 20.920.644/0001-05 |
| Razão social consultoria | MALDONADO CONSULTORIA EMPRESARIAL LTDA — CNPJ 56.082.220/0001-66 |
| Advogado responsável | Dr. Renan Gomes Maldonado de Jesus |
| OAB | OAB/RO 5769 |
| Outro advogado do quadro | Dr. Bruno Vinícius de Souza Faustino — OAB/RO 13021 |
| Gerente Jurídico | Dra. Juliana Ferreira Gusmão de Lara |
| Cidade / Foro | Porto Velho – RO (TJRO) |
| Endereço | Rua Rafael Vaz e Silva, n. 1040, Bairro Nossa Senhora das Graças, CEP 76.804-162 |
| E-mail institucional | maldonadoadvogadopvh@gmail.com |
| WhatsApp | 69 3223-5881 / 69 9846-2865 (escritório) · 69 9369-5030 (consultoria) |
| Agente de IA (nome) | MALDONADO.IA *(substitui "CLAUD.IA")* |
| Nicho | Dívida rural bancária (prorrogação, descaracterização de mora — Tema 28/STJ, revisional bancária) |

## 2. Mapa de substituição (string → string)

| Origem (NÃO pode aparecer) | Substituir por |
|----------------------------|----------------|
| `PAB Advogados`, `PAB` | `Maldonado Advogados`, `Maldonado` |
| `Dra. Pamella Abellan Bovolon` / `Pamella` / `Pam` | `Dr. Renan Gomes Maldonado de Jesus` |
| `OAB/SP 341.431` | `OAB/RO 5769` |
| `São Bernardo do Campo` | `Porto Velho` |
| `pabadvogados@gmail.com` | `maldonadoadvogadopvh@gmail.com` |
| `CLAUD.IA` / `Casal da IA` / `WP` | `MALDONADO.IA` |
| `peca-pamella` / `pamella_format` / `formatar-pamella` | `peca-maldonado` / `maldonado_format` / `formatar-maldonado` |
| `REFERENCIAS_PAMELLA` / `DNA escrita Pamella` | `REFERENCIAS` / `DNA de escrita do escritório` |
| Nomes de pessoas da equipe de origem (Weverton, Gi, Tom, Aneiry...) | papéis genéricos via `config/equipe.py` (ver §4) |
| Nomes de clientes de origem (Romax, PVD, Luciano, Aldenor, Fortec...) | REMOVER (não replicar regras/exceções específicas) |
| `RECLAMANTE / cliente / ATOS INTERNOS...` (estrutura PAB) | estrutura própria do cliente: `ZEUS > 03. CLIENTES > 01 CLIENTES > [LETRA] > cliente > CONTRATO BANCÁRIO / DOC ADMINISTRATIVO / DOC PESSOAL / REUNIÕES - VIA MEET` (ver §7) |

## 3. Credenciais → SEMPRE placeholders vazios

Nenhum token/segredo do escritório de origem pode ser copiado. Tudo vira variável de
ambiente vazia no `config/.env` (o cliente preenche com as credenciais DELE):

```
ANTHROPIC_API_KEY=
ADVBOX_API_TOKEN=
GOOGLE_APPLICATION_CREDENTIALS=config/credentials.json
GOOGLE_TEMPLATE_ID=
GOOGLE_PASTA_DESTINO=
DJEN_OAB_LISTA=          # ex.: 5769-RO,13021-RO
AGENTE_OP_TOKEN=
AGENTE_OP_PORT=8788
```

- IDs de pasta do Drive de origem → vazios (cliente usa a pasta `ZEUS` dele).
- IDs de usuário ADVBOX de origem (147851/61863/73594/...) → vão para `config/equipe.py`, vazios.
- Não copiar ZapSign/Asaas — não fazem parte do escopo contratado por este cliente (sem squad comercial/financeiro nesta fase).

## 4. Equipe / usuários → config central

Em vez de hardcodar pessoas, usar `config/equipe.py`:

```python
USUARIOS_ADVBOX = {
    "RESPONSAVEL": None,   # ID ADVBOX do Dr. Renan Gomes Maldonado de Jesus
    "OUTRO_ADVOGADO": None,  # ID do Dr. Bruno Vinícius de Souza Faustino
    "CONTROLADORIA": None,  # ID de quem hoje faz a triagem manual (controller)
}
USUARIO_PADRAO_TAREFAS = "RESPONSAVEL"  # campo 'from' das tarefas /posts
OABS_MONITORADAS = []  # ex.: [("5769", "RO"), ("13021", "RO")] — para o DJEN
```

O código lê desse config, nunca de IDs fixos do escritório de origem.

## 5. Regras de negócio que NÃO se replicam (são do escritório de origem)

- Squad Financeiro completo (fechamento mensal, comissões Gi/Tom, Asaas) — **fora do escopo contratado** por este cliente nesta fase. Não replicar `FINANCEIRO/`.
- Squad Comercial/Intake com ZapSign/Atende Direito — **fora do escopo contratado** nesta fase (o cliente já usa o fluxo dele para captação). Não replicar `INTAKE/`.
- Exceções de clientes específicos (FORTEC, ROMAX, PVD, AGF, etc.) — remover.
- Dízimo / distribuição de lucros / contas pessoais de sócio de origem — remover.

## 6. Formatação de peças

- Manter o motor de formatação (justificado, citações em bloco) como **padrão do escritório**, calibrado pelos 3 modelos reais (`_uploads_cliente/` em `CS/RENAN_MALDONADO/`).
- Timbrado: usar placeholder `config/timbrado_modelo.docx` (cliente já forneceu Procuração e Contrato de Honorários com o timbrado real — falta isolar um `.docx` só com header/footer).
- Assinatura padrão das peças: **Dr. Renan Gomes Maldonado de Jesus — OAB/RO 5769 — Porto Velho/RO**.

## 7. Estrutura de pastas do cliente (diferente do padrão PAB)

O escritório já usa sua própria convenção — **manter a dele, não impor a nossa**:

```
[Drive do cliente] ZEUS > 03. CLIENTES > 01 CLIENTES > [A] [B] [C] ... [Z] > [NOME DO CLIENTE] >
    CONTRATO BANCÁRIO
    DOC ADMINISTRATIVO
    DOC PESSOAL
    REUNIÕES - VIA MEET
```
IDs de Drive ficam em env (vazios). Não copiar IDs do escritório de origem.

## 8. Checklist de aceitação (passa só se TODOS = OK)

- [ ] `grep -ri "pab\|pamella\|bernardo\|claud.ia\|casal da ia\|weverton" .` retorna **0** em código/docs entregues (exceto este spec e o README, que documentam a origem do motor).
- [ ] Nenhum token real no `.env` (tudo vazio/placeholder).
- [ ] Assinatura e foro = Renan Gomes Maldonado de Jesus / Porto Velho-RO.
- [ ] Imports e nomes de módulo consistentes (sem `pamella_format`).
- [ ] `requirements.txt` idêntico ao núcleo funcional.
