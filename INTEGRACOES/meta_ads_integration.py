"""
Integracao com a Meta Marketing API (Facebook/Instagram Ads) - Maldonado Advogados.

LEITURA: contas, campanhas, insights, leads e custo por lead (relatorio e painel).
CRIACAO: campanha de mensagem no WhatsApp (campanha -> conjunto -> criativo -> anuncio).
  Tudo o que este modulo cria nasce PAUSADO. Ligar e um passo separado (ativar()), que o
  MARKETING/criar_campanha.py so executa depois de confirmacao explicita.

Credenciais em config/.env:
  META_ACCESS_TOKEN    token de Usuario do Sistema (Business Manager > Usuarios do sistema).
                       So relatorio: ads_read. Para criar campanha: ads_management,
                       pages_read_engagement e pages_manage_ads.
  META_AD_ACCOUNT_ID   id da conta de anuncio (com ou sem o prefixo act_)
  META_PAGE_ID         id da Pagina do Facebook do escritorio (a que tem o WhatsApp vinculado)
  META_API_VERSION     opcional (padrao v26.0)

Leitura:  configurado() conta_padrao() listar_contas() listar_campanhas() insights()
          leads(actions) conversas(actions) formularios(actions)
Criacao:  buscar_regiao() buscar_interesse() criar_campanha() criar_conjunto_whatsapp()
          subir_imagem() criar_criativo_whatsapp() criar_anuncio() ativar() pausar()
"""
import json
import logging
import os

import time

import requests

log = logging.getLogger('integracoes.meta_ads')

# acoes que contam como lead do escritorio
ACAO_CONVERSA = 'onsite_conversion.messaging_conversation_started_7d'   # conversa no WhatsApp/Messenger
ACOES_FORMULARIO = ('lead', 'onsite_conversion.lead_grouped', 'offsite_conversion.fb_pixel_lead')

CAMPOS_PADRAO = ('campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,'
                 'spend,impressions,reach,clicks,inline_link_clicks,ctr,cpc,frequency,actions')


def _base():
    return f"https://graph.facebook.com/{os.getenv('META_API_VERSION') or 'v26.0'}"


def get_token():
    tok = os.getenv('META_ACCESS_TOKEN', '')
    if not tok or tok.startswith('SEU') or 'AQUI' in tok.upper():
        return None
    return tok


def conta_padrao():
    conta = (os.getenv('META_AD_ACCOUNT_ID') or '').strip()
    if not conta:
        return None
    return conta if conta.startswith('act_') else f'act_{conta}'


def configurado():
    return bool(get_token() and conta_padrao())


class ErroMeta(RuntimeError):
    pass


def _get(caminho_ou_url, params=None):
    """GET na Graph API. Levanta ErroMeta com a mensagem da API em caso de erro."""
    tok = get_token()
    if not tok:
        raise ErroMeta('META_ACCESS_TOKEN nao configurado em config/.env')
    url = caminho_ou_url if caminho_ou_url.startswith('http') else f'{_base()}/{caminho_ou_url}'
    params = dict(params or {})
    if 'access_token=' not in url:
        params['access_token'] = tok
    # limite de chamadas da conta (codigos 4, 17, 32, 613, 80000-80014): espera e tenta de novo, em vez de cair
    esperas = [60, 180, 300, 600, 900]
    for tentativa in range(len(esperas) + 1):
        try:
            r = requests.get(url, params=params, timeout=90)
        except requests.RequestException as e:
            if tentativa < len(esperas):
                time.sleep(15)
                continue
            raise ErroMeta(f'falha de rede na Meta API: {e}') from e
        if r.status_code == 200:
            return r.json() or {}
        try:
            erro = r.json().get('error', {})
        except ValueError:
            erro = {}
        msg = erro.get('message', r.text[:300])
        codigo = erro.get('code')
        limite = codigo in (4, 17, 32, 613) or (isinstance(codigo, int) and 80000 <= codigo <= 80014) \
            or 'too many calls' in str(msg).lower()
        if limite and tentativa < len(esperas):
            print(f'   Meta: limite de chamadas da conta; aguardando {esperas[tentativa] // 60} min e tentando de novo...')
            time.sleep(esperas[tentativa])
            continue
        raise ErroMeta(f'Meta API {r.status_code}: {msg}')


def _paginar(caminho, params):
    dados = _get(caminho, params)
    linhas = list(dados.get('data', []))
    proxima = (dados.get('paging') or {}).get('next')
    paginas = 0
    while proxima and paginas < 50:
        dados = _get(proxima)
        linhas += dados.get('data', [])
        proxima = (dados.get('paging') or {}).get('next')
        paginas += 1
    return linhas


# ============================================================
# LEITURA
# ============================================================

def listar_contas():
    return _paginar('me/adaccounts', {'fields': 'name,account_id,currency,account_status', 'limit': 100})


def listar_campanhas(conta=None, ativas=False):
    conta = conta or conta_padrao()
    camps = _paginar(f'{conta}/campaigns', {
        'fields': 'name,status,effective_status,objective,daily_budget,lifetime_budget',
        'limit': 200,
    })
    if ativas:
        camps = [c for c in camps if c.get('effective_status') == 'ACTIVE']
    return camps


def insights(obj_id=None, level='ad', desde=None, ate=None, date_preset=None,
             breakdowns=None, campos=CAMPOS_PADRAO):
    """
    Insights da conta (ou de uma campanha) no nivel pedido.
    level: 'campaign' | 'adset' | 'ad'
    desde/ate: 'AAAA-MM-DD' (tem prioridade sobre date_preset)
    breakdowns: ex. 'region' (estado de quem viu o anuncio)
    """
    obj_id = obj_id or conta_padrao()
    params = {'level': level, 'fields': campos, 'limit': 500}
    if desde and ate:
        params['time_range'] = json.dumps({'since': desde, 'until': ate})
    else:
        params['date_preset'] = date_preset or 'last_7d'
    if breakdowns:
        params['breakdowns'] = breakdowns
    return _paginar(f'{obj_id}/insights', params)


def _soma_acoes(actions, tipos):
    total = 0.0
    for a in actions or []:
        if a.get('action_type') in tipos:
            total += float(a.get('value') or 0)
    return int(total)


def conversas(actions):
    return _soma_acoes(actions, (ACAO_CONVERSA,))


def formularios(actions):
    # 'lead' e 'onsite_conversion.lead_grouped' podem vir juntos para o mesmo lead: usa o maior
    return max(_soma_acoes(actions, ('lead',)), _soma_acoes(actions, ('onsite_conversion.lead_grouped',)),
               _soma_acoes(actions, ('offsite_conversion.fb_pixel_lead',)))


def leads(actions):
    """Lead do escritorio = conversa iniciada no WhatsApp + formulario de cadastro."""
    return conversas(actions) + formularios(actions)


# ============================================================
# CRIACAO (escreve na conta de anuncios - tudo nasce PAUSADO)
# ============================================================

def page_id():
    return (os.getenv('META_PAGE_ID') or '').strip() or None


def _post(caminho, dados=None, arquivos=None):
    """POST na Graph API. Campos dict/list viram JSON (exigencia da API)."""
    tok = get_token()
    if not tok:
        raise ErroMeta('META_ACCESS_TOKEN nao configurado em config/.env')
    corpo = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
             for k, v in (dados or {}).items() if v is not None}
    corpo['access_token'] = tok
    r = requests.post(f'{_base()}/{caminho}', data=corpo, files=arquivos, timeout=120)
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code not in (200, 201) or 'error' in j:
        erro = j.get('error', {})
        msg = erro.get('error_user_msg') or erro.get('message') or r.text[:300]
        raise ErroMeta(f'Meta API {r.status_code}: {msg}')
    return j


def buscar_regiao(nome, pais='BR'):
    """Chave do estado para a segmentacao (ex.: 'Rondonia' -> {'key': '...', 'name': 'Rondonia'})."""
    achados = _get('search', {'type': 'adgeolocation', 'location_types': json.dumps(['region']),
                              'q': nome, 'country_code': pais, 'limit': 5}).get('data', [])
    return achados[0] if achados else None


def buscar_interesse(termo, limite=5):
    """Interesses de publico (ex.: 'Agronegocio', 'Pecuaria')."""
    return _get('search', {'type': 'adinterest', 'q': termo, 'limit': limite}).get('data', [])


def criar_campanha(nome, categorias_especiais=None, conta=None):
    """Campanha de engajamento por mensagem (WhatsApp). Orcamento fica no conjunto (ABO)."""
    conta = conta or conta_padrao()
    return _post(f'{conta}/campaigns', {
        'name': nome,
        'objective': 'OUTCOME_ENGAGEMENT',
        'status': 'PAUSED',
        'special_ad_categories': categorias_especiais or [],
        # sem orcamento de campanha: a API exige declarar isso explicitamente
        'is_adset_budget_sharing_enabled': 'false',
    })['id']


def criar_conjunto_whatsapp(campanha_id, nome, orcamento_diario_reais, regioes_chaves,
                            idade_min=25, idade_max=65, interesses=None, conta=None):
    """Conjunto que otimiza para conversas iniciadas no WhatsApp da Pagina."""
    conta = conta or conta_padrao()
    pg = page_id()
    if not pg:
        raise ErroMeta('META_PAGE_ID nao configurado em config/.env')
    targeting = {
        'geo_locations': {'regions': [{'key': k} for k in regioes_chaves], 'location_types': ['home']},
        'age_min': int(idade_min), 'age_max': int(idade_max),
    }
    if interesses:
        targeting['flexible_spec'] = [{'interests': [{'id': i['id'], 'name': i.get('name', '')}
                                                     for i in interesses]}]
    return _post(f'{conta}/adsets', {
        'name': nome,
        'campaign_id': campanha_id,
        'daily_budget': int(round(float(orcamento_diario_reais) * 100)),
        'billing_event': 'IMPRESSIONS',
        'optimization_goal': 'CONVERSATIONS',
        'destination_type': 'WHATSAPP',
        'bid_strategy': 'LOWEST_COST_WITHOUT_CAP',
        'promoted_object': {'page_id': pg},
        'targeting': targeting,
        'status': 'PAUSED',
    })['id']


def subir_imagem(caminho_arquivo, conta=None):
    """Sobe a imagem do anuncio e devolve o hash que o criativo usa."""
    conta = conta or conta_padrao()
    with open(caminho_arquivo, 'rb') as f:
        j = _post(f'{conta}/adimages', arquivos={'filename': (os.path.basename(caminho_arquivo), f)})
    imagens = j.get('images', {})
    return next(iter(imagens.values()))['hash']


def criar_criativo_whatsapp(nome, texto, titulo, image_hash, conta=None):
    """Criativo com botao 'Enviar mensagem' que abre o WhatsApp da Pagina."""
    conta = conta or conta_padrao()
    return _post(f'{conta}/adcreatives', {
        'name': nome,
        'object_story_spec': {
            'page_id': page_id(),
            'link_data': {
                'image_hash': image_hash,
                'message': texto,
                'name': titulo,
                'link': 'https://api.whatsapp.com/send',
                'call_to_action': {'type': 'WHATSAPP_MESSAGE',
                                   'value': {'app_destination': 'WHATSAPP'}},
            },
        },
    })['id']


def criar_anuncio(conjunto_id, criativo_id, nome, conta=None):
    conta = conta or conta_padrao()
    return _post(f'{conta}/ads', {'name': nome, 'adset_id': conjunto_id,
                                  'creative': {'creative_id': criativo_id}, 'status': 'PAUSED'})['id']


def ativar(obj_id):
    """Liga campanha/conjunto/anuncio. So chamar depois de confirmacao humana."""
    return bool(_post(obj_id, {'status': 'ACTIVE'}).get('success'))


def pausar(obj_id):
    return bool(_post(obj_id, {'status': 'PAUSED'}).get('success'))


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             'config', '.env'))
    print('Configurado:', configurado())
    if configurado():
        for c in listar_contas():
            print(' Conta:', c.get('name'), c.get('id'))
