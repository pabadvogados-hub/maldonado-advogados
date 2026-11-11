"""
=============================================================================
  SQUAD FINANCEIRO - MALDONADO ADVOGADOS
=============================================================================

  ADVBOX e a fonte da verdade (contratos e parcelas, por VENCIMENTO).
  O Asaas emite e recebe. Este modulo liga os dois e alimenta a trava do operacional.

  Uso (rodar da raiz do projeto):
    python FINANCEIRO/main.py situacao              # quem esta em dia, em atraso e BLOQUEADO
    python FINANCEIRO/main.py regua                 # mensagens de cobranca do dia, por faixa de atraso
    python FINANCEIRO/main.py historico "NOME" -a "ligou, prometeu pagar dia 20"
    python FINANCEIRO/main.py historico "NOME"      # ver o historico de negociacao
    python FINANCEIRO/main.py saneamento            # contratos que existem num sistema e no outro nao
    python FINANCEIRO/main.py emitir --dias 30      # parcelas do ADVBOX sem cobranca no Asaas (cria com confirmacao)
    python FINANCEIRO/main.py painel                # painel HTML (abre no navegador)

  Saidas em SAIDA/financeiro/ (dado real de cliente - nunca vai para o GitHub).
=============================================================================
"""
import argparse
import csv
import io
import json
import os
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta

if __name__ == '__main__' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'INTEGRACOES'))
sys.path.insert(0, os.path.join(RAIZ, 'config'))

from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, 'config', '.env'))

import advbox_integration as advbox

SAIDA = os.path.join(RAIZ, 'SAIDA', 'financeiro')
ARQ_SITUACAO = os.path.join(SAIDA, 'situacao_clientes.json')
ARQ_HISTORICO = os.path.join(SAIDA, 'historico_negociacao.jsonl')

# Regra combinada na reuniao de 20/10/2026: mais de 3 meses de atraso = cliente bloqueado
DIAS_BLOQUEIO = int(os.getenv('FIN_DIAS_BLOQUEIO') or 90)
# quantos meses para tras o ADVBOX e lido (parcelas antigas em aberto entram na conta)
MESES_HISTORICO = int(os.getenv('FIN_MESES_HISTORICO') or 36)


def _asaas_ok():
    return bool(os.getenv('ASAAS_API_KEY') or os.getenv('ASAAS_API_TOKEN'))


def _norm(txt):
    nfd = unicodedata.normalize('NFD', str(txt or ''))
    return ' '.join(''.join(c for c in nfd if unicodedata.category(c) != 'Mn').upper().split())


def _doc(txt):
    return ''.join(filter(str.isdigit, str(txt or '')))


def chave_cliente(nome, documento=None):
    """CPF/CNPJ quando existe; senao o nome normalizado."""
    d = _doc(documento)
    return d if len(d) in (11, 14) else 'NOME:' + _norm(nome)


def reais(v):
    return 'R$ ' + f'{float(v or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _salvar_json(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


# ============================================================
# SITUACAO POR CLIENTE
# ============================================================

def _parcelas_advbox():
    hoje = date.today()
    inicio = hoje - timedelta(days=30 * MESES_HISTORICO)
    fim = hoje + timedelta(days=60)
    trans = advbox.listar_transacoes({'date_due_start': inicio.isoformat(),
                                      'date_due_end': fim.isoformat()})
    return [t for t in trans if t.get('entry_type') == 'income']


def calcular_situacao():
    """Monta a situacao financeira de cada cliente a partir das parcelas do ADVBOX
    (e do Asaas, quando configurado, para trazer o link de pagamento da cobranca)."""
    hoje = date.today()
    clientes = {}

    for t in _parcelas_advbox():
        if t.get('date_payment'):
            continue
        venc = t.get('date_due')
        if not venc:
            continue
        nome = t.get('name') or 'SEM NOME'
        k = chave_cliente(nome, t.get('identification'))
        c = clientes.setdefault(k, {
            'cliente': nome, 'documento': t.get('identification') or '',
            'em_atraso': 0.0, 'a_vencer': 0.0, 'parcelas_atrasadas': 0,
            'maior_atraso_dias': 0, 'vencimento_mais_antigo': None,
            'processos': [], 'parcelas': [], 'links_pagamento': [],
        })
        valor = float(t.get('amount') or 0)
        dias = (hoje - datetime.strptime(venc[:10], '%Y-%m-%d').date()).days
        if dias > 0:
            c['em_atraso'] += valor
            c['parcelas_atrasadas'] += 1
            c['maior_atraso_dias'] = max(c['maior_atraso_dias'], dias)
            if not c['vencimento_mais_antigo'] or venc < c['vencimento_mais_antigo']:
                c['vencimento_mais_antigo'] = venc[:10]
        else:
            c['a_vencer'] += valor
        if t.get('process_number') and t['process_number'] not in c['processos']:
            c['processos'].append(t['process_number'])
        c['parcelas'].append({'id_advbox': t.get('id'), 'vencimento': venc[:10], 'valor': valor,
                              'dias_atraso': max(dias, 0), 'descricao': (t.get('description') or '')[:120]})

    if _asaas_ok():
        import asaas_integration as asaas
        por_cliente_asaas = {c['id']: c for c in asaas.listar_todos_clientes()}
        for p in asaas.listar_cobrancas(status='OVERDUE'):
            ca = por_cliente_asaas.get(p.get('customer')) or {}
            k = chave_cliente(ca.get('name'), ca.get('cpfCnpj'))
            if k in clientes and p.get('invoiceUrl'):
                clientes[k]['links_pagamento'].append(p['invoiceUrl'])

    for c in clientes.values():
        c['em_atraso'] = round(c['em_atraso'], 2)
        c['a_vencer'] = round(c['a_vencer'], 2)
        if c['maior_atraso_dias'] > DIAS_BLOQUEIO:
            c['status'] = 'BLOQUEADO'
        elif c['maior_atraso_dias'] > 0:
            c['status'] = 'EM_ATRASO'
        else:
            c['status'] = 'EM_DIA'

    dados = {'gerado_em': datetime.now().isoformat(timespec='seconds'),
             'dias_bloqueio': DIAS_BLOQUEIO, 'clientes': clientes}
    _salvar_json(ARQ_SITUACAO, dados)
    return dados


def carregar_situacao(max_horas=24):
    """Usado pela trava do operacional. Recalcula se o arquivo estiver velho."""
    if os.path.exists(ARQ_SITUACAO):
        with open(ARQ_SITUACAO, encoding='utf-8') as f:
            dados = json.load(f)
        idade = datetime.now() - datetime.fromisoformat(dados['gerado_em'])
        if idade < timedelta(hours=max_horas):
            return dados
    return calcular_situacao()


def status_do_cliente(nome, documento=None, situacao=None):
    """'BLOQUEADO' | 'EM_ATRASO' | 'EM_DIA' (sem parcela em aberto = EM_DIA)."""
    situacao = situacao or carregar_situacao()
    c = situacao['clientes'].get(chave_cliente(nome, documento))
    if not c and documento:
        c = situacao['clientes'].get(chave_cliente(nome))
    return (c or {}).get('status', 'EM_DIA'), c


def cmd_situacao(args):
    dados = calcular_situacao()
    cl = list(dados['clientes'].values())
    bloq = [c for c in cl if c['status'] == 'BLOQUEADO']
    atraso = [c for c in cl if c['status'] == 'EM_ATRASO']
    print('=' * 80)
    print('  SITUACAO FINANCEIRA DOS CLIENTES - MALDONADO ADVOGADOS')
    print('=' * 80)
    print(f"  Em atraso (total): {reais(sum(c['em_atraso'] for c in cl))}")
    print(f"  Clientes em atraso: {len(atraso)} | BLOQUEADOS (> {DIAS_BLOQUEIO} dias): {len(bloq)}")
    print(f"  A vencer (60 dias): {reais(sum(c['a_vencer'] for c in cl))}")
    for titulo, lista in (('BLOQUEADOS - operacional nao atua', bloq), ('EM ATRASO', atraso)):
        print(f'\n  --- {titulo} ({len(lista)}) ---')
        for c in sorted(lista, key=lambda x: -x['em_atraso'])[: args.limite]:
            print(f"    {c['cliente'][:40]:40} {reais(c['em_atraso']):>15}  "
                  f"{c['maior_atraso_dias']:>4} dias  {c['parcelas_atrasadas']} parc.")
    print(f'\n  Arquivo da trava do operacional: {ARQ_SITUACAO}')


# ============================================================
# HISTORICO DE NEGOCIACAO (o "campo" que a planilha nao tinha)
# ============================================================

def registrar_historico(cliente, texto, autor=None, documento=None):
    os.makedirs(SAIDA, exist_ok=True)
    reg = {'quando': datetime.now().isoformat(timespec='minutes'), 'cliente': cliente,
           'chave': chave_cliente(cliente, documento), 'autor': autor or os.getenv('FIN_OPERADOR', ''),
           'registro': texto}
    with open(ARQ_HISTORICO, 'a', encoding='utf-8') as f:
        f.write(json.dumps(reg, ensure_ascii=False) + '\n')
    return reg


def ler_historico(cliente=None):
    if not os.path.exists(ARQ_HISTORICO):
        return []
    with open(ARQ_HISTORICO, encoding='utf-8') as f:
        regs = [json.loads(l) for l in f if l.strip()]
    if cliente:
        alvo = _norm(cliente)
        regs = [r for r in regs if alvo in _norm(r['cliente']) or _doc(cliente) == r['chave']]
    return regs


def cmd_historico(args):
    if args.adicionar:
        r = registrar_historico(args.cliente, args.adicionar, args.autor)
        print(f"  Registrado em {r['quando']}: {r['cliente']} - {r['registro']}")
        return
    regs = ler_historico(args.cliente)
    print(f'  Historico de negociacao - {args.cliente} ({len(regs)} registro(s))')
    for r in regs:
        print(f"    {r['quando']}  {r['autor'] or '-':12}  {r['registro']}")


# ============================================================
# REGUA DE COBRANCA
# ============================================================

FAIXAS = [
    # Textos que vao para o cliente. A faixa "bloqueio" fala em suspensao: conferir com a
    # clausula do contrato de honorarios antes de usar.
    (1, 7, 'lembrete',
     'Olá, {primeiro_nome}! Tudo bem? Aqui é do financeiro do Maldonado Advogados. '
     'Consta em aberto a parcela de {valor}, com vencimento em {vencimento}. '
     'Se já pagou, pode desconsiderar. {link_frase}'),
    (8, 30, 'segunda_via',
     'Olá, {primeiro_nome}. Seguimos com {valor} em aberto desde {vencimento}. {link_frase} '
     'Qualquer dificuldade, me chama aqui que a gente resolve.'),
    (31, 90, 'negociacao',
     'Olá, {primeiro_nome}. Há {parcelas} parcela(s) em aberto, somando {valor} (a mais antiga de {vencimento}). '
     'Queremos te ajudar a regularizar: podemos conversar sobre uma forma de pagamento que caiba no seu momento? '
     '{link_frase}'),
    (91, 100000, 'bloqueio',
     'Olá, {primeiro_nome}. O seu contrato está com {valor} em aberto há mais de 90 dias. '
     'Conforme o contrato, a atuação no processo fica suspensa até a regularização. '
     'Fale com o financeiro para negociarmos e retomarmos o seu caso. {link_frase}'),
]


def _faixa(dias):
    for ini, fim, nome, modelo in FAIXAS:
        if ini <= dias <= fim:
            return nome, modelo
    return None, None


def cmd_regua(args):
    dados = calcular_situacao()
    hoje = date.today().isoformat()
    linhas = []
    for c in dados['clientes'].values():
        if c['status'] == 'EM_DIA':
            continue
        faixa, modelo = _faixa(c['maior_atraso_dias'])
        if not faixa:
            continue
        link = c['links_pagamento'][0] if c['links_pagamento'] else ''
        link_frase = (f'Link para pagamento: {link}' if link
                      else 'Se precisar da segunda via, é só me pedir aqui.')
        msg = modelo.format(primeiro_nome=c['cliente'].split()[0].title(), valor=reais(c['em_atraso']),
                            vencimento=datetime.strptime(c['vencimento_mais_antigo'], '%Y-%m-%d').strftime('%d/%m/%Y'),
                            parcelas=c['parcelas_atrasadas'], link_frase=link_frase).strip()
        linhas.append({'cliente': c['cliente'], 'documento': c['documento'], 'faixa': faixa,
                       'dias_atraso': c['maior_atraso_dias'], 'em_atraso': c['em_atraso'],
                       'tem_link_asaas': 'sim' if link else 'nao', 'mensagem': msg})

    os.makedirs(SAIDA, exist_ok=True)
    arq = os.path.join(SAIDA, f'regua_{hoje}.csv')
    with open(arq, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()) if linhas else ['cliente'], delimiter=';')
        w.writeheader()
        w.writerows(linhas)

    por_faixa = defaultdict(int)
    for l in linhas:
        por_faixa[l['faixa']] += 1
        if args.registrar:
            registrar_historico(l['cliente'], f"Regua ({l['faixa']}): mensagem de cobranca gerada",
                                autor='regua', documento=l['documento'])
    print(f'  {len(linhas)} mensagem(ns) de cobranca para hoje: ' +
          ', '.join(f'{k} {v}' for k, v in por_faixa.items()))
    sem_link = sum(1 for l in linhas if l['tem_link_asaas'] == 'nao')
    if sem_link:
        print(f'  {sem_link} sem cobranca no Asaas (rode "emitir" para gerar o link antes de enviar).')
    print(f'  Planilha pronta para o envio pelo WhatsApp do financeiro: {arq}')


# ============================================================
# ADVBOX -> ASAAS (contrato cadastrado gera a cobranca)
# ============================================================

def cmd_emitir(args):
    if not _asaas_ok():
        print('  ASAAS_API_KEY nao configurado em config/.env.')
        return
    import asaas_integration as asaas
    hoje = date.today()
    fim = hoje + timedelta(days=int(args.dias))
    parcelas = [t for t in advbox.listar_transacoes({'date_due_start': hoje.isoformat(),
                                                     'date_due_end': fim.isoformat()})
                if t.get('entry_type') == 'income' and not t.get('date_payment')]
    ja_emitidas = {str(p.get('externalReference')) for p in
                   asaas.listar_cobrancas(due_date_ge=hoje.isoformat(), due_date_le=fim.isoformat())
                   if p.get('externalReference')}
    pendentes = [t for t in parcelas if str(t.get('id')) not in ja_emitidas]
    print(f'  {len(parcelas)} parcela(s) no ADVBOX ate {fim:%d/%m/%Y}; '
          f'{len(pendentes)} ainda sem cobranca no Asaas.')
    clientes_asaas = {_doc(c.get('cpfCnpj')): c for c in asaas.listar_todos_clientes()}
    for t in pendentes:
        nome, doc = t.get('name') or '', _doc(t.get('identification'))
        print(f"\n  {nome} | {reais(t.get('amount'))} | venc. {t.get('date_due')} | {t.get('description') or ''}"[:160])
        if len(doc) not in (11, 14):
            print('    Sem CPF/CNPJ no ADVBOX - completar o cadastro antes de emitir.')
            continue
        if not args.criar:
            continue
        if input('    Emitir a cobranca no Asaas? (s/N): ').strip().lower() != 's':
            continue
        cliente = clientes_asaas.get(doc) or asaas.criar_cliente(nome, doc)
        clientes_asaas[doc] = cliente
        cob = asaas.criar_cobranca(cliente['id'], t.get('amount'), t.get('date_due')[:10],
                                   (t.get('description') or 'Honorarios advocaticios')[:400],
                                   referencia_externa=t.get('id'))
        print(f"    Emitida: {cob.get('invoiceUrl')}")
        registrar_historico(nome, f"Cobranca emitida no Asaas ({reais(t.get('amount'))}, venc. {t.get('date_due')[:10]})",
                            autor='emitir', documento=doc)
    if pendentes and not args.criar:
        print('\n  (Listagem apenas. Para emitir, rode de novo com --criar; cada uma pede confirmacao.)')


# ============================================================
# SANEAMENTO (cruzamento ADVBOX x Asaas)
# ============================================================

def cmd_saneamento(args):
    if not _asaas_ok():
        print('  ASAAS_API_KEY nao configurado em config/.env.')
        return
    import asaas_integration as asaas
    adv = _parcelas_advbox()
    docs_adv = {_doc(t.get('identification')): t.get('name') for t in adv if len(_doc(t.get('identification'))) in (11, 14)}
    nomes_adv = {_norm(t.get('name')) for t in adv}
    clientes_asaas = asaas.listar_todos_clientes()
    com_cobranca = defaultdict(float)
    for p in asaas.listar_cobrancas(due_date_ge=(date.today() - timedelta(days=30 * MESES_HISTORICO)).isoformat()):
        com_cobranca[p.get('customer')] += float(p.get('value') or 0)

    so_asaas = [c for c in clientes_asaas if com_cobranca.get(c['id'])
                and _doc(c.get('cpfCnpj')) not in docs_adv and _norm(c.get('name')) not in nomes_adv]
    docs_asaas = {_doc(c.get('cpfCnpj')) for c in clientes_asaas}
    so_advbox = {d: n for d, n in docs_adv.items() if d not in docs_asaas}
    sem_doc = sorted({t.get('name') for t in adv if len(_doc(t.get('identification'))) not in (11, 14)})

    os.makedirs(SAIDA, exist_ok=True)
    arq = os.path.join(SAIDA, f"saneamento_{date.today().isoformat()}.csv")
    with open(arq, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['situacao', 'cliente', 'documento', 'valor_cobrado_asaas'])
        for c in so_asaas:
            w.writerow(['cobra no Asaas, sem contrato no ADVBOX', c.get('name'), c.get('cpfCnpj'),
                        f"{com_cobranca[c['id']]:.2f}"])
        for d, n in so_advbox.items():
            w.writerow(['contrato no ADVBOX, sem cadastro no Asaas', n, d, ''])
        for n in sem_doc:
            w.writerow(['parcela no ADVBOX sem CPF/CNPJ', n, '', ''])
    print(f'  Cobra no Asaas e nao tem contrato no ADVBOX: {len(so_asaas)}')
    print(f'  Contrato no ADVBOX sem cadastro no Asaas:    {len(so_advbox)}')
    print(f'  Parcelas do ADVBOX sem CPF/CNPJ:              {len(sem_doc)}')
    print(f'  Lista completa: {arq}')


# ============================================================
# PAINEL HTML
# ============================================================

def cmd_painel(args):
    dados = calcular_situacao()
    cl = list(dados['clientes'].values())
    total_atraso = sum(c['em_atraso'] for c in cl)
    faixas = [('1 a 30 dias', 1, 30), ('31 a 90 dias', 31, 90), (f'mais de {DIAS_BLOQUEIO} dias', DIAS_BLOQUEIO + 1, 10 ** 6)]
    resumo_faixas = [(n, sum(c['em_atraso'] for c in cl if a <= c['maior_atraso_dias'] <= b),
                      sum(1 for c in cl if a <= c['maior_atraso_dias'] <= b)) for n, a, b in faixas]
    hist = defaultdict(list)
    for r in ler_historico():
        hist[r['chave']].append(r)

    def linha(c):
        k = chave_cliente(c['cliente'], c['documento'])
        ult = hist.get(k, [])[-1:] or [{}]
        cor = {'BLOQUEADO': 'b', 'EM_ATRASO': 'a'}.get(c['status'], 'd')
        link = f"<a href='{c['links_pagamento'][0]}'>cobranca</a>" if c['links_pagamento'] else '-'
        return (f"<tr><td>{c['cliente']}</td><td><span class='st {cor}'>{c['status'].replace('_', ' ')}</span></td>"
                f"<td class='n'>{reais(c['em_atraso'])}</td><td class='n'>{c['maior_atraso_dias']}</td>"
                f"<td>{ult[0].get('quando', '')[:10]} {ult[0].get('registro', '')[:70]}</td><td>{link}</td></tr>")

    devedores = sorted([c for c in cl if c['em_atraso'] > 0], key=lambda x: -x['em_atraso'])
    cards = ''.join(f"<div class='card'><div class='l'>{n}</div><div class='v'>{reais(v)}</div>"
                    f"<div class='s'>{q} cliente(s)</div></div>" for n, v, q in resumo_faixas)
    html = f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>
<title>Painel Financeiro - Maldonado Advogados</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;background:#0f1720;color:#e6edf3;margin:0;padding:28px}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#8b9bb0;font-size:13px;margin-bottom:22px}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}}
.card{{background:#16212d;border:1px solid #243445;border-radius:8px;padding:16px}}
.card .l{{font-size:12px;color:#8b9bb0;text-transform:uppercase;letter-spacing:1px}}
.card .v{{font-size:24px;font-weight:700;margin-top:6px}} .card .s{{font-size:12px;color:#8b9bb0}}
.card.total .v{{color:#f5c451}}
table{{width:100%;border-collapse:collapse;background:#16212d;border-radius:8px;overflow:hidden;font-size:13px}}
th{{text-align:left;padding:10px;background:#1d2b3a;color:#8b9bb0;font-weight:600}}
td{{padding:9px 10px;border-top:1px solid #243445}} td.n{{text-align:right;white-space:nowrap}}
.st{{padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700}}
.st.b{{background:#5c1d1d;color:#ffb4b4}} .st.a{{background:#5a4512;color:#ffe08a}} .st.d{{background:#123d2a;color:#9be3bd}}
a{{color:#6cb6ff}}
</style></head><body>
<h1>Painel Financeiro</h1>
<div class='sub'>Maldonado Advogados - gerado em {datetime.now():%d/%m/%Y %H:%M} - fonte: ADVBOX (vencimento){' + Asaas' if _asaas_ok() else ''}
 - bloqueio acima de {DIAS_BLOQUEIO} dias</div>
<div class='cards'><div class='card total'><div class='l'>Total em atraso</div><div class='v'>{reais(total_atraso)}</div>
<div class='s'>{len(devedores)} cliente(s)</div></div>{cards}</div>
<table><tr><th>Cliente</th><th>Status</th><th>Em atraso</th><th>Dias</th><th>Ultima negociacao</th><th>Link</th></tr>
{''.join(linha(c) for c in devedores)}</table></body></html>"""
    os.makedirs(SAIDA, exist_ok=True)
    arq = os.path.join(SAIDA, 'painel_financeiro.html')
    with open(arq, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'  Painel gerado: {arq}')
    if not args.nao_abrir:
        import webbrowser
        webbrowser.open('file:///' + arq.replace('\\', '/'))


def main():
    ap = argparse.ArgumentParser(description='Squad Financeiro - Maldonado Advogados')
    sub = ap.add_subparsers(dest='comando')
    p = sub.add_parser('situacao', help='Situacao financeira por cliente (alimenta a trava do operacional)')
    p.add_argument('--limite', type=int, default=40)
    p = sub.add_parser('regua', help='Mensagens de cobranca do dia por faixa de atraso')
    p.add_argument('--registrar', action='store_true', help='Anota no historico de cada cliente')
    p = sub.add_parser('historico', help='Ver ou registrar negociacao de um cliente')
    p.add_argument('cliente')
    p.add_argument('--adicionar', '-a')
    p.add_argument('--autor')
    sub.add_parser('saneamento', help='Cruzamento ADVBOX x Asaas')
    p = sub.add_parser('emitir', help='Parcelas do ADVBOX sem cobranca no Asaas')
    p.add_argument('--dias', default=30)
    p.add_argument('--criar', action='store_true', help='Emite (pede confirmacao em cada uma)')
    p = sub.add_parser('painel', help='Painel HTML do financeiro')
    p.add_argument('--nao-abrir', action='store_true')
    args = ap.parse_args()
    acoes = {'situacao': cmd_situacao, 'regua': cmd_regua, 'historico': cmd_historico,
             'saneamento': cmd_saneamento, 'emitir': cmd_emitir, 'painel': cmd_painel}
    if args.comando in acoes:
        acoes[args.comando](args)
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
