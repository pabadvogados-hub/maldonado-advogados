"""
Hook PreToolUse (Read): impede o Claude de abrir PDF grande inteiro.

PDF lido direto vai pagina por pagina como imagem + texto e e o que mais encarece a peca.
Acima de LIMITE paginas, sem o parametro 'pages', a leitura e bloqueada e o Claude recebe
a instrucao de usar FERRAMENTAS/preparar_caso.py (texto extraido localmente, bem mais barato).
Ler PDF pequeno, ou trechos com pages="1-3", continua liberado.
"""
import json
import os
import sys

LIMITE = int(os.getenv('PDF_LIMITE_PAGINAS') or 5)


def main():
    try:
        dados = json.load(sys.stdin)
    except Exception:
        return 0
    entrada = dados.get('tool_input') or {}
    caminho = entrada.get('file_path') or ''
    if not caminho.lower().endswith('.pdf') or entrada.get('pages'):
        return 0
    try:
        from pypdf import PdfReader
        paginas = len(PdfReader(caminho).pages)
    except Exception:
        return 0     # sem pypdf ou PDF ilegivel: nao atrapalha
    if paginas <= LIMITE:
        return 0
    pasta = os.path.dirname(caminho)
    sys.stderr.write(
        f'PDF com {paginas} paginas: nao ler inteiro (custo alto). Rode primeiro\n'
        f'  python FERRAMENTAS/preparar_caso.py "{pasta}"\n'
        f'e leia o "{os.path.join(pasta, "_CASO.md")}". Se precisar ver uma pagina como imagem '
        f'(assinatura, tabela escaneada), use Read com pages="N".\n')
    return 2


if __name__ == '__main__':
    sys.exit(main())
