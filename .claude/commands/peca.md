---
description: Produz uma peça de dívida rural no fluxo econômico (texto extraído, uma escrita, docx por script)
argument-hint: "<pasta do cliente>" <tipo de ação> [observações]
---

Produza a peça pedida seguindo EXATAMENTE este fluxo, que existe para manter o custo por peça baixo.

Pedido: $ARGUMENTS

1. **Preparar o caso (uma vez):** rode `python FERRAMENTAS/preparar_caso.py "<pasta do cliente>"`.
   Leia SOMENTE o `_CASO.md` gerado. Não abra os PDFs inteiros. Se o `_CASO.md` apontar PDF
   escaneado, leia apenas as páginas que importam (Read com `pages`).
2. **Base jurídica:** use o agente `maldonado-divida-rural` (estrutura e teses) e, só se o caso
   pedir, a nota correspondente em `BASE_CONHECIMENTO/00 - TEMAS/`. Não leia a pasta inteira.
3. **Jurisprudência:** no máximo 2 buscas na web, focadas em TJRO/TRF1. Se não achar precedente
   local, sinalize nos pontos de atenção em vez de continuar buscando.
4. **Escrever uma vez:** escreva a peça completa em Markdown em
   `SAIDA/pecas/<NOME DO CLIENTE> - <AÇÃO> - PRONTA PARA REVISÃO.md`, no formato aceito por
   `FERRAMENTAS/gerar_docx.py` (# título, ## tópicos, > citações, tabelas com |).
   Não reescreva o arquivo inteiro para corrigir detalhe: use edição pontual.
5. **Gerar o Word:** `python FERRAMENTAS/gerar_docx.py "<arquivo .md>"`. Não escreva código python-docx.
6. **Entregar:** caminho do .docx + a lista de pontos de atenção do agente. Não releia a peça
   inteira para "conferir"; os pontos de atenção cobrem a revisão.

Ao terminar, lembre o usuário de rodar `/cost` (custo da peça) e `/clear` antes da próxima peça.
