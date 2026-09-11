"""
=============================================================================
  SQUAD CONTROLADORIA + DIVIDA RURAL - MALDONADO ADVOGADOS
=============================================================================

  Prioridade do projeto: comando `triagem` (Squad Controladoria) — elimina a
  distribuicao manual de intimacoes hoje feita por 2 controllers.

  Uso:
    cd MALDONADO_ADVOGADOS && python OPERACIONAL/main.py triagem --dias 7
    cd MALDONADO_ADVOGADOS && python OPERACIONAL/main.py triagem --dias 7 --criar-tarefa
    cd MALDONADO_ADVOGADOS && python OPERACIONAL/main.py tarefas
    cd MALDONADO_ADVOGADOS && python OPERACIONAL/main.py processos
    cd MALDONADO_ADVOGADOS && python OPERACIONAL/main.py prazos
    cd MALDONADO_ADVOGADOS && python OPERACIONAL/main.py criar-tarefa <lawsuit_id> <tipo> --mensagem "..."
=============================================================================
"""
import sys, os, io, argparse, contextlib
from datetime import datetime, timedelta
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'INTEGRACOES'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))

import requests
import advbox_integration as advbox
import comunica_djen
from triagem_divida_rural import triagem_lote, imprimir_triagem

try:
    import equipe
except ImportError:
    equipe = None


ADVBOX_BASE = 'https://app.advbox.com.br/api/v1'


def _usuarios():
    """Le config/equipe.py (fonte principal) com fallback pro .env."""
    if equipe and equipe.USUARIOS_ADVBOX:
        return equipe.USUARIOS_ADVBOX
    return {
        'RESPONSAVEL': os.getenv('ADVBOX_USER_RESPONSAVEL'),
        'OUTRO_ADVOGADO': os.getenv('ADVBOX_USER_OUTRO_ADVOGADO'),
        'CONTROLADORIA': os.getenv('ADVBOX_USER_CONTROLADORIA'),
    }


def _oabs_monitoradas():
    if equipe and equipe.OABS_MONITORADAS:
        return equipe.OABS_MONITORADAS
    lista = os.getenv('DJEN_OAB_LISTA', '')
    oabs = []
    for par in lista.split(','):
        par = par.strip()
        if '-' in par:
            num, uf = par.split('-', 1)
            oabs.append((num.strip(), uf.strip()))
    return oabs


def _headers():
    token = os.getenv('ADVBOX_API_TOKEN')
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'Maldonado-Advogados/1.0',
    }


# ============================================================
# COMANDO PRIORITARIO: triagem - Squad Controladoria
# ============================================================

class _Tee:
    """Escreve em varios streams ao mesmo tempo (console + arquivo de log)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def cmd_triagem(args):
    if not getattr(args, 'salvar', False):
        _rodar_triagem(args)
        return

    pasta_logs = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(pasta_logs, exist_ok=True)
    nome_arquivo = f"triagem_{datetime.now().strftime('%Y-%m-%d_%H%M')}.txt"
    caminho = os.path.join(pasta_logs, nome_arquivo)
    with open(caminho, 'w', encoding='utf-8') as arquivo:
        tee = _Tee(sys.stdout, arquivo)
        with contextlib.redirect_stdout(tee):
            _rodar_triagem(args)
    print(f'\n  Relatorio salvo em: {caminho}')


def _rodar_triagem(args):
    print('=' * 80)
    print('  TRIAGEM DE CONTROLADORIA - MALDONADO ADVOGADOS')
    print('=' * 80)

    oabs = _oabs_monitoradas()
    if not oabs:
        print('\n  ERRO: nenhuma OAB configurada em config/equipe.py (OABS_MONITORADAS)')
        print('  ou config/.env (DJEN_OAB_LISTA). Sem isso nao ha o que buscar no DJEN.')
        return

    dias = int(args.dias or 1)
    fim = datetime.now().date()
    inicio = fim - timedelta(days=dias - 1)

    print(f'\n  Periodo: {inicio.isoformat()} a {fim.isoformat()}')
    print(f'  OABs monitoradas: {", ".join(f"{n}/{uf}" for n, uf in oabs)}')

    todos_resumos = []
    for numero_oab, uf_oab in oabs:
        print(f'\n  Consultando DJEN para OAB {numero_oab}/{uf_oab}...')
        try:
            itens = comunica_djen.consultar(
                oab_numero=numero_oab, oab_uf=uf_oab,
                data_inicio=inicio.isoformat(), data_fim=fim.isoformat(),
            )
        except RuntimeError as e:
            print(f'  Aviso: falha ao consultar DJEN para {numero_oab}/{uf_oab}: {e}')
            continue
        resumos = [comunica_djen.resumir(i) for i in itens]
        print(f'    {len(resumos)} comunicacao(oes) encontrada(s)')
        todos_resumos.extend(resumos)

    if not todos_resumos:
        print('\n  Nenhuma intimacao/publicacao encontrada no periodo. '
              '(Se isso for inesperado, a API DJEN pode ter dado falso-vazio - tente novamente.)')
        return

    # Cross-reference com o ADVBOX pelo numero do processo (1 consulta por item)
    print('\n  Cruzando com processos no ADVBOX...')
    lawsuits_por_processo = {}
    for r in todos_resumos:
        proc = r.get('processo') or ''
        proc_norm = ''.join(filter(str.isdigit, proc))
        if not proc_norm or proc_norm in lawsuits_por_processo:
            continue
        try:
            achados = advbox.buscar_processo(numero_processo=proc)
        except Exception as e:
            print(f'    Aviso: falha ao buscar processo {proc} no ADVBOX: {e}')
            continue
        if achados:
            lawsuits_por_processo[proc_norm] = achados[0]

    itens_triagem = triagem_lote(todos_resumos, lawsuits_por_processo)
    imprimir_triagem(itens_triagem)

    if args.criar_tarefa:
        _criar_tarefas_da_triagem(itens_triagem)


def _criar_tarefas_da_triagem(itens_triagem):
    """Para itens de prioridade alta com peca/providencia identificada, oferece
    criar a tarefa no ADVBOX - sempre com confirmacao manual, nunca em lote sem revisao.

    Tarefas de triagem saem DA controladoria (from + guest = CONTROLADORIA), nao do
    responsavel pelo escritorio - e a Controladoria quem triA e depois delega pro
    advogado certo (POP-CJ-003), entao a tarefa automatica deve aparecer no nome dela.
    """
    usuarios = _usuarios()
    controladoria_id = usuarios.get('CONTROLADORIA') or usuarios.get('RESPONSAVEL')
    if not controladoria_id:
        print('\n  ERRO: config/equipe.py -> USUARIOS_ADVBOX["CONTROLADORIA"] (ou "RESPONSAVEL") '
              'nao preenchido. Sem isso nao da pra criar tarefa (campo "from" obrigatorio).')
        return

    candidatos = [it for it in itens_triagem if it['prioridade'] == 'alta'
                  and it.get('cliente') and 'NAO ENCONTRADO' not in it['cliente']]

    if not candidatos:
        print('\n  Nenhum item de prioridade alta com processo identificado no ADVBOX para criar tarefa.')
        return

    print(f'\n  {len(candidatos)} item(ns) de prioridade alta prontos para virar tarefa:')
    for it in candidatos:
        print(f"\n  Processo: {it['processo']} | Cliente: {it['cliente']}")
        print(f"  Providencia: {it['providencia_cabivel']}")
        resp = input('  Criar tarefa no ADVBOX para este item? (s/N): ').strip().lower()
        if resp != 's':
            print('  Pulado.')
            continue
        # Aqui e' necessario o lawsuit_id do ADVBOX - buscamos de novo por seguranca.
        achados = advbox.buscar_processo(numero_processo=it['processo'])
        if not achados:
            print('  Processo nao encontrado no ADVBOX no momento da criacao - pulado.')
            continue
        lawsuit_id = achados[0].get('id')
        settings = advbox.carregar_settings()
        task_id = advbox.buscar_id_por_nome('tasks', 'ACOMPANHAMENTO') or (settings.get('tasks') or [{}])[0].get('id')
        try:
            resultado = advbox.criar_publicacao(
                lawsuit_id=lawsuit_id, task_id=task_id, guest_ids=[controladoria_id],
                comments=f"[Triagem automatica] {it['providencia_cabivel']} - {it.get('peca_necessaria') or ''}",
                from_id=controladoria_id, urgent=True,
            )
            print(f'  Tarefa criada: {resultado}')
        except Exception as e:
            print(f'  Erro ao criar tarefa: {e}')


# ============================================================
# COMANDO: tarefas - Lista tarefas pendentes
# ============================================================

def cmd_tarefas(args):
    print('=' * 80)
    print('  TAREFAS PENDENTES - MALDONADO ADVOGADOS')
    print('=' * 80)

    params = {'limit': 100}
    if args.dias:
        inicio = datetime.now() - timedelta(days=30)
        fim = datetime.now() + timedelta(days=int(args.dias))
        params['date_start'] = inicio.strftime('%Y-%m-%d')
        params['date_end'] = fim.strftime('%Y-%m-%d')
    else:
        params['date_start'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        params['date_end'] = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

    r = requests.get(f'{ADVBOX_BASE}/posts', headers=_headers(), params=params, timeout=15)
    data = r.json()
    todas = data.get('data', [])

    pendentes = [t for t in todas if any(not u.get('completed') for u in t.get('users', []))]

    por_resp = defaultdict(list)
    for t in pendentes:
        for u in t.get('users', []):
            if not u.get('completed'):
                nome = u.get('name', 'SEM RESPONSAVEL')
                por_resp[nome].append(t)

    print(f'\n  Total pendentes: {len(pendentes)}')

    for resp in sorted(por_resp.keys()):
        tarefas = por_resp[resp]
        print(f'\n  --- {resp} ({len(tarefas)} tarefas) ---')
        for t in sorted(tarefas, key=lambda x: x.get('date_deadline') or x.get('date', '') or '9'):
            lawsuit = t.get('lawsuit', {}) or {}
            cli = lawsuit['customers'][0].get('name', '') if lawsuit.get('customers') else ''
            prazo = t.get('date_deadline', '')
            prazo_str = f' | PRAZO: {prazo[:10]}' if prazo else ''
            urg = ' [URGENTE]' if any(u.get('urgent') for u in t.get('users', [])) else ''
            notes = (t.get('notes') or '')[:50]
            print(f'    {t.get("date","")[:10]} | {t.get("task","")[:25]:25} | {cli[:25]:25}{urg}{prazo_str}')
            if notes:
                print(f'      {notes}')


# ============================================================
# COMANDO: processos - Lista processos ativos
# ============================================================

def cmd_processos(args):
    print('=' * 80)
    print('  PROCESSOS ATIVOS - MALDONADO ADVOGADOS')
    print('=' * 80)

    data = advbox._request('GET', '/lawsuits', params={'limit': 1000})
    todos = data.get('data', [])
    ativos = [p for p in todos if 'ARQUIV' not in (p.get('stage') or '').upper()
              and 'RENUNCI' not in (p.get('stage') or '').upper()]

    if args.responsavel:
        ativos = [p for p in ativos if args.responsavel.upper() in (p.get('responsible') or '').upper()]

    por_fase = defaultdict(list)
    for p in ativos:
        por_fase[p.get('stage') or 'SEM FASE'].append(p)

    print(f'\n  Total ativos: {len(ativos)}')

    for fase in sorted(por_fase.keys()):
        procs = por_fase[fase]
        print(f'\n  [{fase}] - {len(procs)} processo(s)')
        for p in sorted(procs, key=lambda x: x.get('created_at', ''), reverse=True):
            cli = p.get('customers', [{}])[0].get('name', '') if p.get('customers') else ''
            num = p.get('process_number') or 'S/N'
            resp = (p.get('responsible') or '')[:15]
            print(f'    {num[:35]:35} | {cli[:28]:28} | {resp}')


# ============================================================
# COMANDO: prazos - Lista prazos fatais proximos
# ============================================================

def cmd_prazos(args):
    print('=' * 80)
    print('  PRAZOS FATAIS - PROXIMOS 14 DIAS')
    print('=' * 80)

    inicio = datetime.now()
    fim = inicio + timedelta(days=14)

    r = requests.get(f'{ADVBOX_BASE}/posts', headers=_headers(), params={
        'deadline_start': inicio.strftime('%Y-%m-%d'),
        'deadline_end': fim.strftime('%Y-%m-%d'),
        'limit': 100
    }, timeout=15)
    data = r.json()
    tarefas = data.get('data', [])

    pendentes = [t for t in tarefas if any(not u.get('completed') for u in t.get('users', []))]
    pendentes.sort(key=lambda x: x.get('date_deadline') or '9999')

    print(f'\n  Prazos encontrados: {len(pendentes)}')

    for t in pendentes:
        lawsuit = t.get('lawsuit', {}) or {}
        cli = lawsuit['customers'][0].get('name', '') if lawsuit.get('customers') else ''
        prazo = (t.get('date_deadline') or '')[:10]
        resps = [u.get('name', '')[:20] for u in t.get('users', []) if not u.get('completed')]
        urg = ' [URGENTE]' if any(u.get('urgent') for u in t.get('users', [])) else ''
        notes = (t.get('notes') or '')[:60]

        dias_rest = (datetime.strptime(prazo, '%Y-%m-%d') - datetime.now()).days if prazo else '?'

        print(f'\n  PRAZO: {prazo} ({dias_rest} dias) {urg}')
        print(f'    {t.get("task","")[:30]} | {cli[:30]}')
        print(f'    Responsavel: {", ".join(resps)}')
        if notes:
            print(f'    {notes}')


# ============================================================
# COMANDO: criar-tarefa - Cria tarefa no ADVBOX manualmente
# ============================================================

def cmd_criar_tarefa(args):
    print('Criando tarefa no ADVBOX...')

    settings = advbox.carregar_settings()
    task_types = settings.get('tasks', [])
    task_id = None
    for tt in task_types:
        if args.tipo.upper() in tt.get('task', '').upper():
            task_id = tt['id']
            break
    if not task_id:
        print(f'Tipo de tarefa "{args.tipo}" nao encontrado.')
        print('Tipos disponiveis:')
        for tt in task_types[:20]:
            print(f'  {tt["task"]}')
        return

    usuarios = _usuarios()
    guest_id = usuarios.get(args.para.upper()) if args.para.upper() in usuarios else None
    if not guest_id:
        print(f'Usuario "{args.para}" nao encontrado em config/equipe.py -> USUARIOS_ADVBOX.')
        return
    responsavel_id = usuarios.get('RESPONSAVEL')

    print(f'  Processo: {args.processo}')
    print(f'  Tipo: {args.tipo}')
    print(f'  Para: {args.para} (ID: {guest_id})')
    print(f'  Mensagem: {(args.mensagem or "")[:50]}')

    resp = input('\n  Confirma? (s/N): ').strip().lower()
    if resp != 's':
        print('  Cancelado.')
        return

    resultado = advbox.criar_publicacao(
        lawsuit_id=args.processo, task_id=task_id, guest_ids=[guest_id],
        comments=args.mensagem or '', from_id=responsavel_id,
        date_deadline=args.prazo, urgent=bool(args.urgente),
    )
    print(f'  Tarefa criada! {resultado}')


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Squad Controladoria + Divida Rural - Maldonado Advogados')
    subparsers = parser.add_subparsers(dest='comando')

    p_triagem = subparsers.add_parser('triagem', help='[PRIORIDADE] Triagem de intimacoes/publicacoes via DJEN')
    p_triagem.add_argument('--dias', '-d', default=7, help='Ultimos N dias (default: 7)')
    p_triagem.add_argument('--criar-tarefa', action='store_true',
                            help='Oferece criar tarefa no ADVBOX para itens de prioridade alta (com confirmacao '
                                 'interativa item a item - NAO USAR em execucao agendada/sem terminal, trava '
                                 'esperando resposta)')
    p_triagem.add_argument('--salvar', action='store_true',
                            help='Salva o relatorio em logs/triagem_AAAA-MM-DD_HHMM.txt, alem de mostrar no '
                                 'console - use nas execucoes agendadas (ver deploy/agendar_triagem_*)')

    p_tarefas = subparsers.add_parser('tarefas', help='Listar tarefas pendentes')
    p_tarefas.add_argument('--dias', '-d', help='Dias a frente (default: 14)')

    p_procs = subparsers.add_parser('processos', help='Listar processos ativos')
    p_procs.add_argument('--responsavel', '-r', help='Filtrar por responsavel')

    subparsers.add_parser('prazos', help='Listar prazos fatais proximos')

    p_criar = subparsers.add_parser('criar-tarefa', help='Criar tarefa no ADVBOX')
    p_criar.add_argument('processo', help='ID do processo no ADVBOX')
    p_criar.add_argument('tipo', help='Tipo da tarefa (ex: ACOMPANHAMENTO)')
    p_criar.add_argument('para', help='Responsavel (chave em config/equipe.py, ex: RESPONSAVEL)')
    p_criar.add_argument('--mensagem', '-m', help='Comentario da tarefa')
    p_criar.add_argument('--prazo', '-p', help='Prazo fatal (YYYY-MM-DD)')
    p_criar.add_argument('--urgente', action='store_true', help='Marcar como urgente')

    args = parser.parse_args()

    if args.comando == 'triagem':
        cmd_triagem(args)
    elif args.comando == 'tarefas':
        cmd_tarefas(args)
    elif args.comando == 'processos':
        cmd_processos(args)
    elif args.comando == 'prazos':
        cmd_prazos(args)
    elif args.comando == 'criar-tarefa':
        cmd_criar_tarefa(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
