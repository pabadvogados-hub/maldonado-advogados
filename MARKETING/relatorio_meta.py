"""
RELATORIO DO META ADS - Maldonado Advogados.

Le a conta de anuncios (SOMENTE LEITURA) e entrega, em linguagem simples:
- gasto, alcance, cliques, leads (conversa no WhatsApp + formulario) e custo por lead (CPL);
- comparacao com o periodo anterior de igual tamanho;
- ranking por campanha e por anuncio, e alertas do que merece olhar.

Este relatorio so le. Para CRIAR campanha use MARKETING/criar_campanha.py (sempre nasce PAUSADA
e so e ativada com confirmacao).

  python MARKETING/relatorio_meta.py                 # ultimo dia (diario)
  python MARKETING/relatorio_meta.py --dias 7        # ultimos 7 dias
  python MARKETING/relatorio_meta.py --exemplo       # roda sem token, com dados ficticios
  python MARKETING/relatorio_meta.py --html          # salva tambem em HTML

Credenciais em config/.env: META_ACCESS_TOKEN (Usuario do Sistema, permissao ads_read)
e META_AD_ACCOUNT_ID. Sem elas o script diz exatamente o que falta e nao finge que rodou.
"""
import argparse
import os
import sys
from datetime import date, timedelta

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'INTEGRACOES'))

EXEMPLO = {
    'conta': [{'spend': '1840.55', 'impressions': '98412', 'reach': '41230', 'clicks': '2190',
               'inline_link_clicks': '1870', 'ctr': '2.22', 'frequency': '2.39',
               'actions': [{'action_type': 'onsite_conversion.messaging_conversation_started_7d',
                            'value': '38'},
                           {'action_type': 'lead', 'value': '21'}]}],
    'conta_anterior': [{'spend': '1760.10', 'impressions': '90120', 'reach': '39880',
                        'clicks': '1980', 'inline_link_clicks': '1690', 'ctr': '2.20',
                        'frequency': '2.26',
                        'actions': [{'action_type': 'onsite_conversion.messaging_conversation_started_7d',
                                     'value': '47'},
                                    {'action_type': 'lead', 'value': '18'}]}],
    'campanhas': [
        {'campaign_name': 'ALONGAMENTO RURAL - RO', 'spend': '1120.30', 'impressions': '58210',
         'reach': '24110', 'clicks': '1340', 'inline_link_clicks': '1180', 'ctr': '2.30',
         'actions': [{'action_type': 'onsite_conversion.messaging_conversation_started_7d',
                      'value': '29'}, {'action_type': 'lead', 'value': '15'}]},
        {'campaign_name': 'REVISIONAL CREDITO RURAL - MT', 'spend': '720.25', 'impressions': '40202',
         'reach': '17120', 'clicks': '850', 'inline_link_clicks': '690', 'ctr': '2.11',
         'actions': [{'action_type': 'onsite_conversion.messaging_conversation_started_7d',
                      'value': '9'}, {'action_type': 'lead', 'value': '6'}]},
    ],
    'anuncios': [
        {'ad_name': 'VIDEO produtor - safra frustrada', 'campaign_name': 'ALONGAMENTO RURAL - RO',
         'spend': '610.10', 'impressions': '31020', 'clicks': '820', 'inline_link_clicks': '740',
         'ctr': '2.64', 'frequency': '2.10',
         'actions': [{'action_type': 'onsite_conversion.messaging_conversation_started_7d',
                      'value': '22'}, {'action_type': 'lead', 'value': '11'}]},
        {'ad_name': 'ESTATICO - banco cobrando a parcela', 'campaign_name': 'ALONGAMENTO RURAL - RO',
         'spend': '510.20', 'impressions': '27190', 'clicks': '520', 'inline_link_clicks': '440',
         'ctr': '1.91', 'frequency': '3.90', 'actions': []},
        {'ad_name': 'CARROSSEL - prorrogacao da divida', 'campaign_name': 'REVISIONAL CREDITO RURAL - MT',
         'spend': '720.25', 'impressions': '40202', 'clicks': '850', 'inline_link_clicks': '690',
         'ctr': '2.11', 'frequency': '2.35',
         'actions': [{'action_type': 'onsite_conversion.messaging_conversation_started_7d',
                      'value': '9'}, {'action_type': 'lead', 'value': '6'}]},
    ],
}


def reais(v):
    return 'R$ ' + f'{float(v or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def num(v):
    return f'{int(float(v or 0)):,}'.replace(',', '.')


def periodos(dias, hoje=None):
    """O periodo fecha em ONTEM: o dia corrente ainda esta incompleto na Meta."""
    hoje = hoje or date.today()
    ate = hoje - timedelta(days=1)
    desde = ate - timedelta(days=dias - 1)
    ate_ant = desde - timedelta(days=1)
    desde_ant = ate_ant - timedelta(days=dias - 1)
    return (desde.isoformat(), ate.isoformat()), (desde_ant.isoformat(), ate_ant.isoformat())


def metricas(linha):
    import meta_ads_integration as meta
    gasto = float(linha.get('spend') or 0)
    acoes = linha.get('actions')
    conv, form = meta.conversas(acoes), meta.formularios(acoes)
    leads = conv + form
    cliques = float(linha.get('inline_link_clicks') or linha.get('clicks') or 0)
    return {
        'gasto': gasto,
        'alcance': float(linha.get('reach') or 0),
        'impressoes': float(linha.get('impressions') or 0),
        'cliques': cliques,
        'conversas': conv,
        'formularios': form,
        'leads': leads,
        'cpl': gasto / leads if leads else None,
        'ctr': float(linha.get('ctr') or 0),
        'frequencia': float(linha.get('frequency') or 0),
    }


def soma(linhas):
    if not linhas:
        return metricas({})
    total = {}
    for linha in linhas:
        for k, v in metricas(linha).items():
            if k in ('cpl', 'ctr', 'frequencia'):
                continue
            total[k] = (total.get(k) or 0) + (v or 0)
    total['cpl'] = total['gasto'] / total['leads'] if total.get('leads') else None
    base = metricas(linhas[0])
    total['ctr'], total['frequencia'] = base['ctr'], base['frequencia']
    return total


def variacao(atual, anterior):
    if not anterior:
        return None
    return (atual - anterior) / anterior * 100


def seta(pct, bom_subir=True):
    if pct is None:
        return 's/ base'
    simbolo = '+' if pct >= 0 else ''
    bom = (pct >= 0) == bom_subir
    return f'{simbolo}{pct:.0f}% ({"melhor" if bom else "pior"})'


def coletar(dias, exemplo=False):
    if exemplo:
        d = dict(EXEMPLO)
        (d1, a1), (d0, a0) = periodos(dias)
        d['periodo'], d['periodo_anterior'] = [d1, a1], [d0, a0]
        return d

    import meta_ads_integration as meta
    if not meta.configurado():
        raise SystemExit(
            'Meta Ads nao configurado. Preencha em config/.env:\n'
            '  META_ACCESS_TOKEN   = token de Usuario do Sistema do Business Manager DELA\n'
            '                        (Configuracoes do Negocio > Usuarios do sistema), com\n'
            '                        permissao ads_read na conta de anuncios\n'
            '  META_AD_ACCOUNT_ID  = id da conta de anuncios (act_...)\n'
            'Para ver o formato do relatorio sem credencial: --exemplo')

    (d1, a1), (d0, a0) = periodos(dias)
    print(f'   lendo {d1} a {a1} (comparando com {d0} a {a0})')
    try:
        return {
            'periodo': [d1, a1], 'periodo_anterior': [d0, a0],
            'conta': meta.insights(level='account', desde=d1, ate=a1),
            'conta_anterior': meta.insights(level='account', desde=d0, ate=a0),
            'campanhas': meta.insights(level='campaign', desde=d1, ate=a1),
            'anuncios': meta.insights(level='ad', desde=d1, ate=a1),
        }
    except meta.ErroMeta as e:
        raise SystemExit(f'ERRO na Meta API: {e}')


def alertas(a, ant, campanhas, anuncios):
    saida = []
    v_cpl = variacao(a['cpl'] or 0, ant['cpl'] or 0) if (a['cpl'] and ant['cpl']) else None
    if v_cpl is not None and v_cpl > 20:
        saida.append(f'Custo por lead subiu {v_cpl:.0f}% contra o periodo anterior '
                     f'({reais(ant["cpl"])} -> {reais(a["cpl"])}).')
    if not a['leads'] and a['gasto']:
        saida.append(f'{reais(a["gasto"])} gastos e NENHUM lead no periodo. Conferir se o evento '
                     f'de conversao esta marcado certo antes de concluir que a campanha e ruim.')
    for ad in anuncios:
        m = metricas(ad)
        if m['gasto'] >= 100 and not m['leads']:
            saida.append(f'Anuncio "{ad.get("ad_name")}" gastou {reais(m["gasto"])} sem nenhum lead.')
        if m['frequencia'] >= 3.5:
            saida.append(f'Anuncio "{ad.get("ad_name")}" com frequencia {m["frequencia"]:.1f} - '
                         f'o mesmo publico ja viu muitas vezes (publico cansado).')
    for c in campanhas:
        m = metricas(c)
        if m['leads'] and a['cpl'] and m['cpl'] and m['cpl'] > a['cpl'] * 1.5:
            saida.append(f'Campanha "{c.get("campaign_name")}" com CPL {reais(m["cpl"])}, bem acima '
                         f'da media da conta ({reais(a["cpl"])}).')
    if not saida:
        saida.append('Nenhum alerta no periodo.')
    return saida


def texto(d, dias):
    a, ant = soma(d['conta']), soma(d.get('conta_anterior') or [])
    L = []
    P = L.append
    titulo = 'RELATORIO DIARIO' if dias == 1 else f'RELATORIO DE {dias} DIAS'
    P(f'{titulo} - META ADS - MALDONADO ADVOGADOS')
    P(f'Periodo: {d["periodo"][0]} a {d["periodo"][1]}  '
      f'(anterior: {d["periodo_anterior"][0]} a {d["periodo_anterior"][1]})')
    P('')
    P('RESUMO')
    P(f'  Investido ............ {reais(a["gasto"])}   {seta(variacao(a["gasto"], ant["gasto"]))}')
    P(f'  Leads ................ {num(a["leads"])}   '
      f'(WhatsApp {num(a["conversas"])} + formulario {num(a["formularios"])})   '
      f'{seta(variacao(a["leads"], ant["leads"]))}')
    P(f'  Custo por lead (CPL) . {reais(a["cpl"]) if a["cpl"] else "sem lead"}   '
      f'{seta(variacao(a["cpl"] or 0, ant["cpl"] or 0), bom_subir=False) if (a["cpl"] and ant["cpl"]) else ""}')
    P(f'  Alcance / cliques .... {num(a["alcance"])} pessoas / {num(a["cliques"])} cliques no link')
    P('')
    P('POR CAMPANHA')
    for c in sorted(d.get('campanhas') or [], key=lambda x: -float(x.get('spend') or 0)):
        m = metricas(c)
        P(f'  {c.get("campaign_name", "?")[:46]:46} {reais(m["gasto"]):>13}  '
          f'{num(m["leads"]):>4} leads  CPL {reais(m["cpl"]) if m["cpl"] else "-"}')
    P('')
    P('ANUNCIOS (do que mais gastou para o que menos gastou)')
    for ad in sorted(d.get('anuncios') or [], key=lambda x: -float(x.get('spend') or 0))[:10]:
        m = metricas(ad)
        P(f'  {ad.get("ad_name", "?")[:46]:46} {reais(m["gasto"]):>13}  '
          f'{num(m["leads"]):>4} leads  CPL {reais(m["cpl"]) if m["cpl"] else "-"}  '
          f'CTR {m["ctr"]:.2f}%')
    P('')
    P('O QUE OLHAR')
    for al in alertas(a, ant, d.get('campanhas') or [], d.get('anuncios') or []):
        P(f'  - {al}')
    P('')
    P('Nada foi alterado na conta: pausar, ativar ou mudar orcamento e decisao humana, no '
      'Gerenciador de Anuncios.')
    P('Lead = conversa iniciada no WhatsApp + formulario de cadastro. Se a conta usa outro '
      'evento de conversao, avisar para ajustar antes de usar o CPL como meta.')
    return '\n'.join(L)


def html(conteudo):
    corpo = conteudo.replace('&', '&amp;').replace('<', '&lt;')
    return ('<!doctype html><meta charset="utf-8">'
            '<title>Meta Ads - Maldonado Advogados</title>'
            '<style>body{margin:0;background:#0f1115;color:#e7e9ee;'
            'font:14px/1.6 ui-monospace,Consolas,monospace}'
            'main{max-width:900px;margin:0 auto;padding:32px 16px}'
            'pre{white-space:pre-wrap;word-break:break-word;margin:0}</style>'
            f'<main><pre>{corpo}</pre></main>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dias', type=int, default=1, help='tamanho do periodo (padrao 1 = diario)')
    ap.add_argument('--exemplo', action='store_true', help='dados ficticios, sem tocar na Meta')
    ap.add_argument('--html', action='store_true', help='salva tambem em HTML')
    a = ap.parse_args()

    if a.dias < 1:
        sys.exit('--dias deve ser 1 ou mais.')

    if not a.exemplo:
        try:
            from dotenv import load_dotenv
            load_dotenv(os.path.join(RAIZ, 'config', '.env'))
        except ImportError:
            pass

    d = coletar(a.dias, exemplo=a.exemplo)
    conteudo = texto(d, a.dias)
    print()
    print(conteudo)

    pasta = os.path.join(RAIZ, 'SAIDA', 'meta')
    os.makedirs(pasta, exist_ok=True)
    base = f'META_{d["periodo"][0]}_a_{d["periodo"][1]}' + ('_EXEMPLO' if a.exemplo else '')
    caminho = os.path.join(pasta, base + '.txt')
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(conteudo + '\n')
    print(f'\nSalvo em: {caminho}')
    if a.html:
        caminho_html = os.path.join(pasta, base + '.html')
        with open(caminho_html, 'w', encoding='utf-8') as f:
            f.write(html(conteudo))
        print(f'HTML:     {caminho_html}')


if __name__ == '__main__':
    main()
