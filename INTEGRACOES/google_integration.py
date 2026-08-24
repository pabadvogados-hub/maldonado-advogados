"""
Integração com Google Drive/Docs/Calendar - Maldonado Advogados

Modulo enxuto (auth + helpers genericos). NAO inclui geracao de documento por
template fixo (Ficha/Contrato/Procuracao) porque o Squad Comercial/Intake nao
faz parte do escopo contratado por este cliente nesta fase - ver
docs/_WHITE_LABEL_SPEC.md secao 5. Quando o cliente definir o formato de peca
final (DOCX gerado pelo Claude, ou template Google Docs com placeholders
{{CHAVE}}), usar preencher_documento() abaixo.
"""
import os
import sys
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar'
]


def autenticar_google():
    """
    Autentica com OAuth2 (conta do escritorio) se oauth_credentials.json existir.
    Caso contrario, usa Service Account como fallback.
    """
    project_root = os.path.join(os.path.dirname(__file__), '..')
    config_dir = os.path.join(project_root, 'config')
    oauth_creds_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS", os.path.join(config_dir, "oauth_credentials.json"))
    token_path = os.path.join(config_dir, "token.json")
    sa_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", os.path.join(config_dir, "credentials.json"))

    creds = None

    if os.path.exists(oauth_creds_path):
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Renovando token de acesso...")
                creds.refresh(Request())
            else:
                print("Abrindo navegador para login com a conta Google do escritorio...")
                print("(isso so precisa ser feito uma vez)")
                flow = InstalledAppFlow.from_client_secrets_file(oauth_creds_path, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        print("Autenticado com a conta Google do escritorio!")

    elif os.path.exists(sa_creds_path):
        print("AVISO: Usando Service Account (cota limitada).")
        print("Para usar a conta do escritorio, configure oauth_credentials.json")
        creds = service_account.Credentials.from_service_account_file(
            sa_creds_path, scopes=SCOPES)
    else:
        print("ERRO: Nenhum arquivo de credenciais encontrado.")
        print("Coloque 'oauth_credentials.json' ou 'credentials.json' na pasta config/.")
        sys.exit(1)

    try:
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        return drive_service, docs_service
    except Exception as e:
        print(f"ERRO DE AUTENTICACAO: {str(e)}")
        sys.exit(1)


def buscar_pasta_por_nome(drive_service, nome: str, pasta_pai_id: str = None):
    """Busca uma pasta pelo nome (opcionalmente dentro de um pai). Retorna o ID ou None.

    Uso tipico no escritorio: navegar a estrutura dele (ZEUS > 03. CLIENTES > 01 CLIENTES
    > [LETRA] > [NOME DO CLIENTE]) sem hardcodar IDs de pasta.
    """
    query = f"name = '{nome}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    if pasta_pai_id:
        query += f" and '{pasta_pai_id}' in parents"
    resultado = drive_service.files().list(q=query, fields='files(id, name)').execute()
    arquivos = resultado.get('files', [])
    return arquivos[0]['id'] if arquivos else None


def preencher_documento(docs_service, document_id: str, dados: dict):
    """
    Edita um documento Google via BatchUpdate substituindo placeholders {{CHAVE}}
    pelos valores do dicionario. Uso: gerar peca a partir de um template com marcadores.
    """
    print("Preenchendo documento...")

    requests = []
    for chave, valor in dados.items():
        if not isinstance(valor, str):
            valor = str(valor)
        requests.append({
            'replaceAllText': {
                'containsText': {'text': f"{{{{{chave}}}}}", 'matchCase': True},
                'replaceText': valor
            }
        })

    try:
        docs_service.documents().batchUpdate(
            documentId=document_id, body={'requests': requests}).execute()
        print("Documento finalizado com sucesso.")
    except HttpError as error:
        print("ERRO DE API DOCS: falha ao formatar o texto do arquivo.")
        print(f"Detalhes: {error}")
        sys.exit(1)


# ============================================================
# GOOGLE CALENDAR — convites de prazo (Squad Controladoria)
# ============================================================

def _calendar_service():
    """Servico do Calendar reusando o token OAuth (mesma conta do Drive)."""
    config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
    token_path = os.path.join(config_dir, 'token.json')
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    return build('calendar', 'v3', credentials=creds)


def criar_evento_prazo(titulo, data_ymd, descricao='', convidados=None, hora_inicio='09:00', duracao_min=60):
    """Cria um evento no Google Agenda para um prazo fatal e envia convite pros e-mails da equipe.

    data_ymd: 'YYYY-MM-DD'
    convidados: lista de e-mails (recebem convite; sendUpdates=all)
    Retorna o link do evento, ou None se falhar.
    """
    try:
        cal = _calendar_service()
        h, m = (hora_inicio.split(':') + ['00'])[:2]
        fim_min = int(h) * 60 + int(m) + duracao_min
        fim_h, fim_m = divmod(fim_min, 60)
        body = {
            'summary': titulo,
            'description': descricao,
            'start': {'dateTime': f'{data_ymd}T{int(h):02d}:{int(m):02d}:00', 'timeZone': 'America/Porto_Velho'},
            'end': {'dateTime': f'{data_ymd}T{fim_h:02d}:{fim_m:02d}:00', 'timeZone': 'America/Porto_Velho'},
            'attendees': [{'email': e} for e in (convidados or [])],
            'reminders': {'useDefault': False, 'overrides': [
                {'method': 'popup', 'minutes': 60}, {'method': 'email', 'minutes': 1440}]},
        }
        ev = cal.events().insert(calendarId='primary', body=body, sendUpdates='all').execute()
        print(f'   Evento na agenda criado: {titulo} ({data_ymd}) -> {ev.get("htmlLink")}')
        return ev.get('htmlLink')
    except Exception as e:
        print(f'   Aviso: falha ao criar evento na agenda: {e}')
        return None
