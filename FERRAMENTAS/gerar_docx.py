"""
GERAR DOCX - converte a peca escrita em Markdown para .docx no timbrado do escritorio.

Por que existe: sem este script, o Claude escreve (e corrige) codigo python-docx a cada peca,
o que gasta muitos tokens de saida - os mais caros. Com ele, o Claude escreve a peca em
.md uma vez e roda um comando.

  python FERRAMENTAS/gerar_docx.py peca.md
  python FERRAMENTAS/gerar_docx.py peca.md --saida "SAIDA/pecas/JOAO - REVISIONAL - PRONTA PARA REVISAO.docx"

Markdown aceito:
  # TITULO            -> titulo centralizado, negrito, maiusculo
  ## Subtitulo        -> negrito
  ### Subtitulo menor -> negrito
  > citacao           -> recuo de 4 cm, italico, fonte menor (lei, sumula, julgado)
  **negrito**  *italico*
  | a | b |           -> tabela (ex.: juros compostos x capitalizacao)
  ---                 -> quebra de pagina
  paragrafo normal    -> justificado, recuo de primeira linha

Timbrado: DOCS_MODELOS/timbrado_modelo.docx (ou o caminho em DOCS_MODELOS_TIMBRADO no .env).
O conteudo do modelo e apagado e so o cabecalho/rodape/estilos ficam.
"""
import argparse
import io
import os
import re
import sys

if __name__ == '__main__' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FONTE = os.getenv('PECA_FONTE') or ''          # vazio = usa a fonte do timbrado
TAMANHO = float(os.getenv('PECA_TAMANHO') or 12)
RECUO_PRIMEIRA_LINHA_CM = float(os.getenv('PECA_RECUO_CM') or 2.5)
ENTRELINHAS = float(os.getenv('PECA_ENTRELINHAS') or 1.5)


def _documento_base():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, 'config', '.env'))
    modelo = os.path.join(RAIZ, os.getenv('DOCS_MODELOS_TIMBRADO') or 'DOCS_MODELOS/timbrado_modelo.docx')
    if not os.path.exists(modelo):
        print(f'  Aviso: timbrado nao encontrado em {modelo} - gerando sem timbrado.')
        return Document()
    doc = Document(modelo)
    corpo = doc.element.body
    for el in list(corpo):
        if not el.tag.endswith('sectPr'):      # mantem margens/cabecalho/rodape
            corpo.remove(el)
    return doc


def _runs(par, texto, italico_base=False, tamanho=None):
    """Aplica **negrito** e *italico* inline."""
    for pedaco in re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', texto):
        if not pedaco:
            continue
        negrito = pedaco.startswith('**') and pedaco.endswith('**')
        italico = not negrito and pedaco.startswith('*') and pedaco.endswith('*')
        limpo = pedaco[2:-2] if negrito else pedaco[1:-1] if italico else pedaco
        r = par.add_run(limpo)
        r.bold = negrito or None
        r.italic = (italico or italico_base) or None
        if FONTE:
            r.font.name = FONTE
        r.font.size = Pt(tamanho or TAMANHO)


def _formatar(par, alinhamento=WD_ALIGN_PARAGRAPH.JUSTIFY, recuo_primeira=None, recuo_esq=None):
    fmt = par.paragraph_format
    par.alignment = alinhamento
    fmt.line_spacing = ENTRELINHAS
    fmt.space_after = Pt(6)
    if recuo_primeira is not None:
        fmt.first_line_indent = Cm(recuo_primeira)
    if recuo_esq is not None:
        fmt.left_indent = Cm(recuo_esq)


def _tabela(doc, linhas):
    celulas = [[c.strip() for c in l.strip().strip('|').split('|')] for l in linhas
               if not re.fullmatch(r'\|?[\s:\-|]+\|?', l.strip())]
    if not celulas:
        return
    t = doc.add_table(rows=0, cols=max(len(c) for c in celulas))
    t.style = 'Table Grid'
    for i, linha in enumerate(celulas):
        row = t.add_row().cells
        for j, txt in enumerate(linha):
            par = row[j].paragraphs[0]
            _runs(par, f'**{txt}**' if i == 0 else txt, tamanho=TAMANHO - 1)
    doc.add_paragraph()


def converter(md_path, saida):
    doc = _documento_base()
    with open(md_path, encoding='utf-8') as f:
        linhas = f.read().splitlines()
    i = 0
    while i < len(linhas):
        l = linhas[i].rstrip()
        if not l.strip():
            i += 1
            continue
        if l.strip() == '---':
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        elif l.startswith('|'):
            bloco = []
            while i < len(linhas) and linhas[i].startswith('|'):
                bloco.append(linhas[i])
                i += 1
            _tabela(doc, bloco)
            continue
        elif l.startswith('# '):
            p = doc.add_paragraph()
            _runs(p, f'**{l[2:].strip().upper()}**')
            _formatar(p, WD_ALIGN_PARAGRAPH.CENTER)
        elif l.startswith('## ') or l.startswith('### '):
            p = doc.add_paragraph()
            _runs(p, f"**{l.lstrip('#').strip()}**")
            _formatar(p)
        elif l.startswith('>'):
            p = doc.add_paragraph()
            _runs(p, l.lstrip('>').strip(), italico_base=True, tamanho=TAMANHO - 1)
            _formatar(p, recuo_esq=4)
            p.paragraph_format.line_spacing = 1.0
        else:
            p = doc.add_paragraph()
            _runs(p, l.strip())
            _formatar(p, recuo_primeira=RECUO_PRIMEIRA_LINHA_CM)
        i += 1
    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    doc.save(saida)
    return saida


def main():
    ap = argparse.ArgumentParser(description='Markdown -> .docx no timbrado do escritorio')
    ap.add_argument('markdown')
    ap.add_argument('--saida', help='caminho do .docx (padrao: mesmo nome do .md)')
    args = ap.parse_args()
    saida = args.saida or os.path.splitext(args.markdown)[0] + '.docx'
    print(f'  Peca gerada: {converter(args.markdown, saida)}')


if __name__ == '__main__':
    main()
