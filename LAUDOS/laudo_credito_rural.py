"""
LAUDO DE CALCULO DO CREDITO RURAL - Maldonado Advogados

Substitui o laudo contratado de terceiro: recalcula a cedula de credito rural em dois cenarios
sobre os MESMOS eventos (liberacoes e pagamentos) e mostra a diferenca no saldo devedor.

  Cenario COBRADO ...... taxa e capitalizacao que o banco aplicou (contrato/extrato)
  Cenario RECALCULADO .. taxa e capitalizacao que o advogado definir como devidas

Os parametros juridicos do recalculo (limite de juros, periodicidade de capitalizacao,
encargos) sao ESCOLHA DO ADVOGADO e vao no arquivo do caso, com o fundamento escrito. O script
nao decide tese: ele calcula, mostra a memoria de calculo e gera a minuta do laudo em .docx.

  python LAUDOS/laudo_credito_rural.py LAUDOS/exemplo_cedula.json
  python LAUDOS/laudo_credito_rural.py caso.json --saida SAIDA/laudos/

Arquivo do caso (JSON) - ver LAUDOS/exemplo_cedula.json:
  devedor, credor, cedula, data_base (AAAA-MM-DD)
  liberacoes: [{data, valor}]   pagamentos: [{data, valor}]
  cobrado / recalculado: {taxa_aa (% nominal ao ano), capitalizacao: mensal|semestral|anual|simples,
                          fundamento (texto livre, vai no laudo)}
"""
import argparse
import io
import json
import os
import sys
from datetime import date, datetime

if __name__ == '__main__' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESES_PERIODO = {'mensal': 1, 'semestral': 6, 'anual': 12}


def _d(txt):
    return datetime.strptime(txt[:10], '%Y-%m-%d').date()


def reais(v):
    return 'R$ ' + f'{float(v or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _somar_meses(d, meses):
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    dias_mes = [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return date(ano, mes, min(d.day, dias_mes))


def calcular(liberacoes, pagamentos, data_base, taxa_aa, capitalizacao):
    """
    Evolucao do saldo devedor. Juros correm pro rata dia (ano de 365 dias) sobre o capital.
    - capitalizacao periodica: os juros acumulados viram capital a cada aniversario do periodo,
      contado da 1a liberacao;
    - 'simples': juros nunca viram capital.
    Pagamento abate primeiro os juros vencidos e depois o capital (art. 354 do Codigo Civil).
    Devolve (linhas da memoria de calculo, saldo final).
    """
    taxa_dia = float(taxa_aa) / 100 / 365
    eventos = [(_d(l['data']), 'Liberação', float(l['valor'])) for l in liberacoes]
    eventos += [(_d(p['data']), 'Pagamento', float(p['valor'])) for p in pagamentos]
    inicio = min(e[0] for e in eventos)
    fim = _d(data_base)
    if capitalizacao in MESES_PERIODO:
        n, d = 1, _somar_meses(inicio, MESES_PERIODO[capitalizacao])
        while d <= fim:
            eventos.append((d, 'Capitalização', 0.0))
            n += 1
            d = _somar_meses(inicio, MESES_PERIODO[capitalizacao] * n)
    elif capitalizacao != 'simples':
        raise ValueError(f'capitalizacao invalida: {capitalizacao}')
    eventos.append((fim, 'Data-base', 0.0))
    ordem = {'Liberação': 0, 'Capitalização': 1, 'Pagamento': 2, 'Data-base': 3}
    eventos.sort(key=lambda e: (e[0], ordem[e[1]]))

    capital = juros = 0.0
    ultimo = inicio
    linhas = []
    for dia, tipo, valor in eventos:
        juros += capital * taxa_dia * (dia - ultimo).days
        ultimo = dia
        if tipo == 'Liberação':
            capital += valor
        elif tipo == 'Capitalização':
            if juros < 0.005:
                continue
            capital += juros
            juros = 0.0
        elif tipo == 'Pagamento':
            abate_juros = min(valor, juros)
            juros -= abate_juros
            capital -= valor - abate_juros
        linhas.append({'data': dia.isoformat(), 'evento': tipo, 'valor': round(valor, 2),
                       'capital': round(capital, 2), 'juros_em_aberto': round(juros, 2),
                       'saldo': round(capital + juros, 2)})
    return linhas, round(capital + juros, 2)


def _tabela(doc, linhas, titulo):
    from docx.shared import Pt
    doc.add_paragraph().add_run(titulo).bold = True
    t = doc.add_table(rows=1, cols=6)
    t.style = 'Table Grid'
    for i, h in enumerate(('Data', 'Evento', 'Valor', 'Capital', 'Juros em aberto', 'Saldo')):
        t.rows[0].cells[i].text = h
    for l in linhas:
        if l['evento'] == 'Capitalização' and len(linhas) > 60:
            continue  # memoria completa vai no anexo .csv; a tabela do laudo fica legivel
        c = t.add_row().cells
        c[0].text = _d(l['data']).strftime('%d/%m/%Y')
        c[1].text = l['evento']
        c[2].text = reais(l['valor']) if l['valor'] else '-'
        c[3].text = reais(l['capital'])
        c[4].text = reais(l['juros_em_aberto'])
        c[5].text = reais(l['saldo'])
    for row in t.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(8)


def gerar_laudo(caso, pasta_saida):
    import csv
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    cob, rec = caso['cobrado'], caso['recalculado']
    l_cob, s_cob = calcular(caso['liberacoes'], caso.get('pagamentos', []), caso['data_base'],
                            cob['taxa_aa'], cob['capitalizacao'])
    l_rec, s_rec = calcular(caso['liberacoes'], caso.get('pagamentos', []), caso['data_base'],
                            rec['taxa_aa'], rec['capitalizacao'])
    diferenca = round(s_cob - s_rec, 2)

    timbrado = os.path.join(RAIZ, os.getenv('DOCS_MODELOS_TIMBRADO') or 'DOCS_MODELOS/timbrado_modelo.docx')
    doc = Document(timbrado) if os.path.exists(timbrado) else Document()
    titulo = doc.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    titulo.add_run('LAUDO TÉCNICO DE RECÁLCULO - CÉDULA DE CRÉDITO RURAL').bold = True
    aviso = doc.add_paragraph()
    aviso.add_run('MINUTA PARA REVISÃO DO ADVOGADO - conferir os dados com o contrato e o extrato do banco '
                  'antes de juntar.').italic = True

    doc.add_paragraph().add_run('1. IDENTIFICAÇÃO').bold = True
    for rot, chave in (('Devedor', 'devedor'), ('Credor', 'credor'), ('Cédula', 'cedula'),
                       ('Processo', 'processo')):
        if caso.get(chave):
            doc.add_paragraph(f'{rot}: {caso[chave]}')
    doc.add_paragraph(f"Data-base do cálculo: {_d(caso['data_base']).strftime('%d/%m/%Y')}")
    total_lib = sum(float(l['valor']) for l in caso['liberacoes'])
    total_pag = sum(float(p['valor']) for p in caso.get('pagamentos', []))
    doc.add_paragraph(f'Valor liberado: {reais(total_lib)} | Valor pago até a data-base: {reais(total_pag)}')

    doc.add_paragraph().add_run('2. METODOLOGIA').bold = True
    doc.add_paragraph(
        'Os dois cenários usam os mesmos eventos (liberações e pagamentos). Os juros correm pro rata die, '
        'em ano de 365 dias. Na capitalização periódica, os juros acumulados são incorporados ao capital a '
        'cada período contado da primeira liberação; nos juros simples, nunca são incorporados. Cada '
        'pagamento quita primeiro os juros vencidos e depois o capital (art. 354 do Código Civil).')
    doc.add_paragraph(f"Cenário cobrado: {cob['taxa_aa']}% ao ano, capitalização {cob['capitalizacao']}. "
                      f"{cob.get('fundamento', '')}")
    doc.add_paragraph(f"Cenário recalculado: {rec['taxa_aa']}% ao ano, capitalização {rec['capitalizacao']}. "
                      f"{rec.get('fundamento', '')}")

    doc.add_paragraph().add_run('3. RESULTADO').bold = True
    t = doc.add_table(rows=4, cols=2)
    t.style = 'Table Grid'
    for i, (a, b) in enumerate((('Saldo devedor - cenário cobrado', reais(s_cob)),
                                ('Saldo devedor - cenário recalculado', reais(s_rec)),
                                ('Diferença (cobrado a maior)', reais(diferenca)),
                                ('Diferença sobre o saldo cobrado',
                                 f'{(diferenca / s_cob * 100 if s_cob else 0):.2f}%'.replace('.', ',')))):
        t.cell(i, 0).text, t.cell(i, 1).text = a, b

    doc.add_paragraph().add_run('4. MEMÓRIA DE CÁLCULO').bold = True
    _tabela(doc, l_cob, 'Cenário cobrado')
    _tabela(doc, l_rec, 'Cenário recalculado')
    doc.add_paragraph().add_run('5. CONCLUSÃO').bold = True
    doc.add_paragraph(caso.get('conclusao') or '[Advogado: escrever a conclusão técnica e o pedido.]')
    doc.add_paragraph(f"{os.getenv('ESCRITORIO_CIDADE') or ''}, {date.today().strftime('%d/%m/%Y')}.")
    doc.add_paragraph(os.getenv('ESCRITORIO_ASSINATURA') or '')

    os.makedirs(pasta_saida, exist_ok=True)
    base = ''.join(ch if ch.isalnum() or ch in ' -_' else '_' for ch in
                   f"Laudo - {caso.get('devedor', 'caso')} - {caso.get('cedula', '')}").strip()
    arq_docx = os.path.join(pasta_saida, base + '.docx')
    doc.save(arq_docx)
    arq_csv = os.path.join(pasta_saida, base + ' - memoria.csv')
    with open(arq_csv, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['cenario', 'data', 'evento', 'valor', 'capital', 'juros_em_aberto', 'saldo'])
        for nome, linhas in (('cobrado', l_cob), ('recalculado', l_rec)):
            for l in linhas:
                w.writerow([nome, l['data'], l['evento'], l['valor'], l['capital'], l['juros_em_aberto'], l['saldo']])
    return {'saldo_cobrado': s_cob, 'saldo_recalculado': s_rec, 'diferenca': diferenca,
            'docx': arq_docx, 'csv': arq_csv}


def main():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, 'config', '.env'))
    ap = argparse.ArgumentParser(description='Laudo de recalculo de cedula de credito rural')
    ap.add_argument('caso', help='arquivo JSON do caso (ver LAUDOS/exemplo_cedula.json)')
    ap.add_argument('--saida', default=os.path.join(RAIZ, 'SAIDA', 'laudos'))
    args = ap.parse_args()
    with open(args.caso, encoding='utf-8') as f:
        caso = json.load(f)
    r = gerar_laudo(caso, args.saida)
    print(f"  Saldo cobrado:      {reais(r['saldo_cobrado'])}")
    print(f"  Saldo recalculado:  {reais(r['saldo_recalculado'])}")
    print(f"  Diferenca:          {reais(r['diferenca'])}")
    print(f"  Laudo (minuta):     {r['docx']}")
    print(f"  Memoria completa:   {r['csv']}")


if __name__ == '__main__':
    main()
