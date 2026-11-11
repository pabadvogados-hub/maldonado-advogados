"""
CRIA CAMPANHA NO META ADS - Maldonado Advogados (mensagem no WhatsApp para produtor rural).

Le MARKETING/campanha_produtor_rural.json (textos, estados, orcamento) e monta
campanha -> conjuntos -> anuncios. TUDO NASCE PAUSADO: nada gasta dinheiro ate o --ativar.

  python MARKETING/criar_campanha.py                       # mostra o plano, nao cria nada
  python MARKETING/criar_campanha.py --criar               # cria tudo PAUSADO e mostra os IDs
  python MARKETING/criar_campanha.py --ativar <campanha_id> # liga campanha, conjuntos e anuncios (pede confirmacao)
  python MARKETING/criar_campanha.py --pausar <campanha_id>
  python MARKETING/criar_campanha.py --config outro.json   # outra campanha

Precisa em config/.env: META_ACCESS_TOKEN (com ads_management), META_AD_ACCOUNT_ID e META_PAGE_ID
(a Pagina do escritorio com o WhatsApp Business vinculado). Os resultados aparecem no
MARKETING/relatorio_meta.py (gasto, conversas, custo por lead).
"""
import argparse
import io
import json
import os
import sys

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'INTEGRACOES'))

from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, 'config', '.env'))

import meta_ads_integration as meta

PASTA_CRIATIVOS = os.path.join(RAIZ, 'MARKETING', 'criativos')


def carregar(caminho):
    with open(caminho, encoding='utf-8') as f:
        return json.load(f)


def faltando(cfg):
    falta = []
    if not meta.get_token():
        falta.append('META_ACCESS_TOKEN no config/.env')
    if not meta.conta_padrao():
        falta.append('META_AD_ACCOUNT_ID no config/.env')
    if not meta.page_id():
        falta.append('META_PAGE_ID no config/.env (Pagina com o WhatsApp vinculado)')
    for a in cfg['anuncios']:
        if not os.path.exists(os.path.join(PASTA_CRIATIVOS, a['imagem'])):
            falta.append(f"imagem MARKETING/criativos/{a['imagem']} (anuncio '{a['nome']}')")
    return falta


def mostrar_plano(cfg):
    total = sum(c['orcamento_diario_reais'] for c in cfg['conjuntos'])
    print('=' * 78)
    print(f"  CAMPANHA: {cfg['nome_campanha']}")
    print(f'  Objetivo: conversas no WhatsApp | Orcamento total: R$ {total:.2f}/dia (~R$ {total * 30:.0f}/mes)')
    print('=' * 78)
    for c in cfg['conjuntos']:
        print(f"\n  Conjunto: {c['nome']} | {', '.join(c['estados'])} | {c['idade_min']}-{c['idade_max']} anos"
              f" | R$ {c['orcamento_diario_reais']:.2f}/dia | interesses: {', '.join(c.get('interesses') or ['aberto'])}")
    for a in cfg['anuncios']:
        print(f"\n  Anuncio: {a['nome']}  (imagem {a['imagem']})\n    Titulo: {a['titulo']}")
        for l in a['texto'].splitlines():
            print(f'    {l}')


def criar(cfg):
    camp = meta.criar_campanha(cfg['nome_campanha'], cfg.get('categorias_especiais'))
    print(f'\n  Campanha criada (PAUSADA): {camp}')
    criativos = []
    for a in cfg['anuncios']:
        h = meta.subir_imagem(os.path.join(PASTA_CRIATIVOS, a['imagem']))
        cid = meta.criar_criativo_whatsapp(a['nome'], a['texto'], a['titulo'], h)
        criativos.append((a['nome'], cid))
        print(f"  Criativo: {a['nome']} -> {cid}")
    for c in cfg['conjuntos']:
        regioes = []
        for uf in c['estados']:
            r = meta.buscar_regiao(uf)
            if not r:
                raise meta.ErroMeta(f'Estado nao encontrado na Meta: {uf}')
            regioes.append(r['key'])
        interesses = []
        for termo in c.get('interesses') or []:
            achados = meta.buscar_interesse(termo, 1)
            if achados:
                interesses.append(achados[0])
        cj = meta.criar_conjunto_whatsapp(camp, c['nome'], c['orcamento_diario_reais'], regioes,
                                          c['idade_min'], c['idade_max'], interesses)
        print(f"  Conjunto: {c['nome']} -> {cj}")
        for nome, cid in criativos:
            ad = meta.criar_anuncio(cj, cid, f"{c['nome']} | {nome}")
            print(f'    Anuncio: {nome} -> {ad}')
    print(f'\n  Tudo criado PAUSADO. Confira no Gerenciador de Anuncios e, para ligar:')
    print(f'    python MARKETING/criar_campanha.py --ativar {camp}')
    return camp


def _filhos(campanha_id):
    conj = meta._paginar(f'{campanha_id}/adsets', {'fields': 'id,name', 'limit': 100})
    ads = meta._paginar(f'{campanha_id}/ads', {'fields': 'id,name', 'limit': 200})
    return conj, ads


def mudar_status(campanha_id, ligar):
    conj, ads = _filhos(campanha_id)
    acao = 'LIGAR' if ligar else 'PAUSAR'
    print(f'  {acao}: campanha {campanha_id}, {len(conj)} conjunto(s), {len(ads)} anuncio(s).')
    if ligar and input('  A campanha passa a gastar o orcamento diario. Confirma? (s/N): ').strip().lower() != 's':
        print('  Cancelado.')
        return
    f = meta.ativar if ligar else meta.pausar
    for obj in [*ads, *conj, {'id': campanha_id, 'name': 'campanha'}]:
        print(f"    {obj['name'][:50]:50} {'ok' if f(obj['id']) else 'FALHOU'}")


def main():
    ap = argparse.ArgumentParser(description='Cria campanha de WhatsApp no Meta Ads')
    ap.add_argument('--config', default=os.path.join(RAIZ, 'MARKETING', 'campanha_produtor_rural.json'))
    ap.add_argument('--criar', action='store_true')
    ap.add_argument('--ativar', metavar='CAMPANHA_ID')
    ap.add_argument('--pausar', metavar='CAMPANHA_ID')
    args = ap.parse_args()

    try:
        if args.ativar:
            return mudar_status(args.ativar, True)
        if args.pausar:
            return mudar_status(args.pausar, False)
        cfg = carregar(args.config)
        mostrar_plano(cfg)
        falta = faltando(cfg)
        if falta:
            print('\n  Para criar falta:')
            for f in falta:
                print(f'    - {f}')
            return
        if not args.criar:
            print('\n  (So o plano. Para criar PAUSADO na conta, rode com --criar.)')
            return
        criar(cfg)
    except meta.ErroMeta as e:
        print(f'\n  ERRO da Meta: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
