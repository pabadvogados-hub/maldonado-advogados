"""
Integracao com a API Asaas - Maldonado Advogados.
Consulta cobrancas e clientes e cria LINK DE PAGAMENTO da entrada.

API Base: https://api.asaas.com/v3
Auth: header access_token (chave do Asaas do escritorio, em config/.env)

Por que link de pagamento e nao cobranca nominal: POST /customers exige cpfCnpj;
POST /paymentLinks nao exige - o proprio cliente preenche os dados no checkout.
Isso e o que permite o comercial gerar o link na hora da venda, sem depender do
financeiro e sem ter o documento do cliente em maos.
"""
import os
import sys
import time
import requests


ASAAS_BASE_URL = os.getenv('ASAAS_BASE_URL', 'https://api.asaas.com/v3')


def _get_token():
    token = os.getenv('ASAAS_API_KEY') or os.getenv('ASAAS_API_TOKEN')
    if not token:
        print('ERRO: ASAAS_API_KEY nao encontrado no config/.env')
        sys.exit(1)
    return token


def _headers():
    return {
        'access_token': _get_token(),
        'User-Agent': 'Maldonado-Advogados/1.0',
    }


def _request(method, endpoint, params=None, json_data=None, retries=2):
    url = f'{ASAAS_BASE_URL}{endpoint}'
    for tentativa in range(retries + 1):
        try:
            resp = requests.request(method, url, headers=_headers(),
                                    params=params, json=json_data, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get('Retry-After', 10))
                print(f'  Rate limit Asaas. Aguardando {wait}s...')
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.exceptions.HTTPError:
            print(f'  Asaas erro ({resp.status_code}): {resp.text[:200]}')
            if tentativa < retries and resp.status_code >= 500:
                time.sleep(3)
                continue
            raise
        except requests.exceptions.RequestException as e:
            print(f'  Asaas conexao falhou: {e}')
            if tentativa < retries:
                time.sleep(3)
                continue
            raise
    return None


# ============================================================
# LINK DE PAGAMENTO (entrada de honorarios)
# ============================================================

def criar_link_pagamento(nome, valor, descricao=None, max_parcelas=1,
                         dias_validade=7, billing_type='UNDEFINED'):
    """
    Cria um link de pagamento no Asaas e devolve a resposta da API.

    nome: aparece no checkout (ex.: 'Honorarios - Revisional - Joao da Silva')
    valor: float, em reais
    max_parcelas: 1 = sem parcelamento; >1 libera parcelado no cartao
    billing_type: 'UNDEFINED' (cliente escolhe pix/boleto/cartao), 'PIX',
                  'BOLETO' ou 'CREDIT_CARD'
    dias_validade: o link para de aceitar pagamento depois disso (None = sem fim)

    NAO exige CPF/CNPJ do cliente - ele preenche no checkout.
    """
    from datetime import date, timedelta

    payload = {
        'name': nome,
        'description': descricao or nome,
        'billingType': billing_type,
        'chargeType': 'DETACHED',
        'value': round(float(valor), 2),
        'dueDateLimitDays': 7,
    }
    if max_parcelas and int(max_parcelas) > 1:
        payload['maxInstallmentCount'] = int(max_parcelas)
    if dias_validade:
        payload['endDate'] = (date.today() + timedelta(days=int(dias_validade))).isoformat()

    return _request('POST', '/paymentLinks', json_data=payload)


def obter_link_pagamento(link_id):
    return _request('GET', f'/paymentLinks/{link_id}')


def cobrancas_do_link(link_id):
    """Cobrancas geradas por um link - serve para saber se o cliente pagou."""
    data = _request('GET', '/payments', params={'paymentLink': link_id, 'limit': 100})
    return data.get('data', []) if data else []


# ============================================================
# COBRANCAS (PAYMENTS)
# ============================================================

def listar_cobrancas(status=None, customer=None, due_date_ge=None,
                     due_date_le=None, limit=100):
    """
    Lista cobrancas do Asaas.

    status: 'PENDING', 'OVERDUE', 'RECEIVED', 'CONFIRMED' etc.
    due_date_ge / due_date_le: YYYY-MM-DD (filtra por vencimento)
    """
    todas = []
    offset = 0
    while True:
        params = {'limit': limit, 'offset': offset}
        if status:
            params['status'] = status
        if customer:
            params['customer'] = customer
        if due_date_ge:
            params['dueDate[ge]'] = due_date_ge
        if due_date_le:
            params['dueDate[le]'] = due_date_le

        data = _request('GET', '/payments', params=params)
        registros = data.get('data', []) if data else []
        todas.extend(registros)
        if not (data or {}).get('hasMore') or not registros:
            break
        offset += limit

    return todas


def listar_cobrancas_abertas(dias_ate_vencer=7):
    """Cobrancas vencidas (OVERDUE) + PENDING que vencem nos proximos N dias."""
    from datetime import date, timedelta

    hoje = date.today()
    limite_aviso = hoje + timedelta(days=dias_ate_vencer)

    vencidas = listar_cobrancas(status='OVERDUE')
    a_vencer = listar_cobrancas(
        status='PENDING',
        due_date_ge=hoje.isoformat(),
        due_date_le=limite_aviso.isoformat(),
    )

    for p in vencidas:
        p['_situacao'] = 'VENCIDA'
    for p in a_vencer:
        p['_situacao'] = 'A_VENCER'

    return vencidas + a_vencer


def obter_linha_digitavel(payment_id):
    try:
        data = _request('GET', f'/payments/{payment_id}/identificationField')
        return data.get('identificationField') if data else None
    except Exception:
        return None


def obter_pix_qrcode(payment_id):
    """PIX do boleto: encodedImage (base64), payload (copia-e-cola), expirationDate."""
    try:
        data = _request('GET', f'/payments/{payment_id}/pixQrCode')
        if data and data.get('success'):
            return data
        return None
    except Exception:
        return None


# ============================================================
# CLIENTES
# ============================================================

def obter_cliente(customer_id):
    return _request('GET', f'/customers/{customer_id}')


def listar_clientes(cpf=None, nome=None, email=None, limit=100):
    params = {'limit': limit}
    if cpf:
        params['cpfCnpj'] = cpf
    if nome:
        params['name'] = nome
    if email:
        params['email'] = email
    data = _request('GET', '/customers', params=params)
    return data.get('data', []) if data else []


def listar_todos_clientes():
    """Todos os clientes da conta (paginado) - base do cruzamento com o ADVBOX."""
    todos, offset = [], 0
    while True:
        data = _request('GET', '/customers', params={'limit': 100, 'offset': offset})
        registros = data.get('data', []) if data else []
        todos.extend(registros)
        if not (data or {}).get('hasMore') or not registros:
            break
        offset += 100
    return todos


def criar_cliente(nome, cpf_cnpj, email=None, telefone=None):
    """Cadastra o cliente no Asaas (exige CPF/CNPJ). Devolve o registro criado."""
    payload = {'name': nome, 'cpfCnpj': ''.join(filter(str.isdigit, str(cpf_cnpj)))}
    if email:
        payload['email'] = email
    if telefone:
        payload['mobilePhone'] = ''.join(filter(str.isdigit, str(telefone)))
    return _request('POST', '/customers', json_data=payload)


def criar_cobranca(customer_id, valor, vencimento, descricao, billing_type='UNDEFINED',
                   parcelas=None, referencia_externa=None):
    """
    Cria a cobranca no Asaas (boleto/pix/cartao - UNDEFINED deixa o cliente escolher).

    vencimento: 'AAAA-MM-DD'. parcelas: N > 1 gera parcelamento de 'valor' total.
    referencia_externa: id da transacao do ADVBOX - e o que amarra os dois sistemas.
    """
    payload = {
        'customer': customer_id,
        'billingType': billing_type,
        'dueDate': vencimento,
        'description': descricao,
    }
    if parcelas and int(parcelas) > 1:
        payload['installmentCount'] = int(parcelas)
        payload['totalValue'] = round(float(valor), 2)
    else:
        payload['value'] = round(float(valor), 2)
    if referencia_externa:
        payload['externalReference'] = str(referencia_externa)
    return _request('POST', '/payments', json_data=payload)


def testar_conexao():
    print('Testando conexao Asaas...')
    try:
        data = _request('GET', '/myAccount')
        if data:
            print(f'  Conta: {data.get("name", "?")}')
            print(f'  Email: {data.get("email", "?")}')
            return True
    except Exception as e:
        print(f'  ERRO: {e}')
    return False


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))
    testar_conexao()
