"""
PREPARAR CASO - transforma os PDFs do cliente num texto enxuto ANTES de chamar o Claude.

Por que existe: quando o Claude le um PDF direto, cada pagina vai como imagem + texto e
custa muito mais do que o mesmo conteudo em texto puro. Num processo de 200 paginas isso
vira a maior parte do custo da peca. Aqui a extracao e feita no seu computador, de graca,
e o Claude le so o arquivo .md gerado.

  python FERRAMENTAS/preparar_caso.py "C:/caminho/da/pasta/do/cliente"
  python FERRAMENTAS/preparar_caso.py contrato.pdf extrato.pdf --saida SAIDA/casos/joao

O que faz:
  - extrai o texto de cada PDF, pagina por pagina (marca [arquivo p. N] para citar depois);
  - tira cabecalho/rodape repetido em todas as paginas, linhas em branco e numeracao solta;
  - avisa quais PDFs sao escaneados (sem texto): esses precisam de OCR ou de leitura
    pontual pelo Claude, SO das paginas que importam (Read com o parametro pages).
Saida: <pasta>/_CASO.md + um resumo no terminal com o tamanho estimado em tokens.
"""
import argparse
import io
import os
import re
import sys
from collections import Counter

if __name__ == '__main__' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from pypdf import PdfReader
except ImportError:
    print('Falta a biblioteca pypdf:  pip install pypdf')
    sys.exit(1)

MIN_CARACTERES_PAGINA = 40   # abaixo disso a pagina e tratada como imagem (escaneada)


def _paginas(caminho):
    leitor = PdfReader(caminho)
    return [(p.extract_text() or '') for p in leitor.pages]


def _limpar(paginas):
    """Remove linhas que se repetem em mais da metade das paginas (cabecalho/rodape)."""
    contagem = Counter()
    for txt in paginas:
        contagem.update({l.strip() for l in txt.splitlines() if l.strip()})
    limite = max(3, len(paginas) // 2)
    repetidas = {l for l, n in contagem.items() if n >= limite and len(l) < 150}
    limpas = []
    for txt in paginas:
        linhas = []
        for l in txt.splitlines():
            l = re.sub(r'[ \t]+', ' ', l).strip()
            if not l or l in repetidas or re.fullmatch(r'(p[aá]g(ina)?\.?\s*)?\d+(\s*(de|/)\s*\d+)?', l, re.I):
                continue
            linhas.append(l)
        limpas.append('\n'.join(linhas))
    return limpas


def preparar(arquivos, pasta_saida):
    os.makedirs(pasta_saida, exist_ok=True)
    partes, escaneados, resumo = [], [], []
    for arq in arquivos:
        nome = os.path.basename(arq)
        try:
            brutas = _paginas(arq)
        except Exception as e:
            resumo.append(f'  ERRO ao ler {nome}: {e}')
            continue
        limpas = _limpar(brutas)
        sem_texto = [i + 1 for i, t in enumerate(limpas) if len(t) < MIN_CARACTERES_PAGINA]
        if len(sem_texto) == len(limpas):
            escaneados.append((nome, len(limpas)))
            continue
        partes.append(f'\n\n# {nome} ({len(limpas)} p.)')
        for i, txt in enumerate(limpas, 1):
            if len(txt) >= MIN_CARACTERES_PAGINA:
                partes.append(f'\n[{nome} p. {i}]\n{txt}')
        if sem_texto:
            resumo.append(f'  {nome}: paginas sem texto (imagem): {sem_texto[:30]}')

    texto = ''.join(partes).strip()
    cab = ['# CASO PREPARADO PARA O CLAUDE',
           'Ler ESTE arquivo em vez dos PDFs. Citar pela marcacao [arquivo p. N].']
    if escaneados:
        cab.append('\nPDFs ESCANEADOS (sem texto - ler so as paginas necessarias, com Read + pages):')
        cab += [f'- {n} ({p} p.)' for n, p in escaneados]
    saida = os.path.join(pasta_saida, '_CASO.md')
    with open(saida, 'w', encoding='utf-8') as f:
        f.write('\n'.join(cab) + '\n\n' + texto + '\n')

    tokens = len(texto) // 4
    print(f'  Caso preparado: {saida}')
    print(f'  Tamanho: {len(texto):,} caracteres (~{tokens:,} tokens)'.replace(',', '.'))
    for l in resumo:
        print(l)
    if escaneados:
        print('  Escaneados (sem texto): ' + ', '.join(n for n, _ in escaneados))
    if tokens > 60000:
        print('  ATENCAO: caso grande. Peca ao Claude para ler por partes ou corte anexos que nao importam.')
    return saida


def main():
    ap = argparse.ArgumentParser(description='Extrai o texto dos PDFs do caso para o Claude ler barato')
    ap.add_argument('entradas', nargs='+', help='pasta do cliente ou arquivos .pdf')
    ap.add_argument('--saida', help='pasta onde salvar o _CASO.md (padrao: a propria pasta)')
    args = ap.parse_args()
    arquivos = []
    for e in args.entradas:
        if os.path.isdir(e):
            for raiz, _, nomes in os.walk(e):
                arquivos += [os.path.join(raiz, n) for n in sorted(nomes) if n.lower().endswith('.pdf')]
        elif e.lower().endswith('.pdf'):
            arquivos.append(e)
    if not arquivos:
        print('  Nenhum PDF encontrado.')
        return
    pasta = args.saida or (args.entradas[0] if os.path.isdir(args.entradas[0])
                           else os.path.dirname(os.path.abspath(args.entradas[0])))
    preparar(arquivos, pasta)


if __name__ == '__main__':
    main()
