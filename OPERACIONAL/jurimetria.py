# -*- coding: utf-8 -*-
"""
Jurimetria - Maldonado Advogados
=================================
Constroi o banco de teses (vault Obsidian, BASE_CONHECIMENTO/) de forma
INCREMENTAL, a partir dos dados reais que ja passam pela triagem diaria
(DJEN + ADVBOX). Nao existe "botao magico" que traz o perfil de qualquer
magistrado sob demanda: Jusbrasil, Escavador e a propria busca de
jurisprudencia do TJRO bloqueiam acesso automatizado (HTTP 403 / bloqueio
antirrobo - testado em 11/09/2026). O que este modulo faz de verdade:

1. Extrai o nome do magistrado do TEXTO OFICIAL da comunicacao (quando
   presente - e' o que consta em "Relator(a):", "Juiz(a):" etc.) - nunca
   busca em site nenhum, nunca inventa nome.
2. Registra uma nota de CASO em BASE_CONHECIMENTO/02 - CASOS/ pra cada
   intimacao processada pela triagem.
3. Cria/atualiza uma nota de MAGISTRADO em BASE_CONHECIMENTO/01 - MAGISTRADOS/
   (separado por TJRO x JUSTICA_FEDERAL) com a lista de casos observados -
   com o tempo, isso vira um HISTORICO REAL de como aquele juiz decide nos
   temas do escritorio, construido pelo proprio fluxo de trabalho.

Chamado automaticamente pelo `triagem` (OPERACIONAL/main.py) a cada rodada -
so escreve arquivo local, nao mexe em ADVBOX nem exige confirmacao.
"""
import os
import re
import unicodedata
from datetime import datetime

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', 'BASE_CONHECIMENTO')
PASTA_CASOS = os.path.join(BASE_DIR, '02 - CASOS')
PASTA_MAGISTRADOS = os.path.join(BASE_DIR, '01 - MAGISTRADOS')

# Federal quando a comunicacao vem de orgao com "FEDERAL" no nome/tribunal
# (TRF, Justica Federal, Vara Federal) - o resto vai pra TJRO por padrao,
# que e' o foro da maior parte da carteira (dividas com bancos privados/
# cooperativas). Nao e' uma classificacao perfeita, so uma heuristica.
def _e_federal(tribunal, orgao):
    junto = f'{tribunal or ""} {orgao or ""}'.upper()
    return 'FEDERAL' in junto or 'TRF' in junto


# So o padrao "RELATOR(A):" e' confiavel o suficiente pra extrair sem risco -
# e' um rotulo padronizado dos tribunais que SEMPRE vem seguido do cargo e do
# nome completo (nunca de outra coisa). Testado e removido um padrao anterior
# que confundia "JUIZO" (o FORUM) com "JUIZ" (a PESSOA) e gerava lixo tipo
# "Da_Causa.md" a partir de trechos como "JUIZO DE DIREITO DA ... EXIGIDA
# PARA A CONCESSAO ...". Melhor extrair de menos comunicacoes do que
# registrar magistrado errado.
_PADRAO_RELATOR = re.compile(
    r'RELATOR\(?A?\)?\s*:?\s*(?P<cargo>DESEMBARGADORA|DESEMBARGADOR|JU[IÍ]ZA|JU[IÍ]Z)\s+'
    r'(?P<nome>[A-ZÀ-Ú][A-ZÀ-Ú\.\s]{4,60}?)(?=\s{2,}|[\n,\.]|$)',
    re.IGNORECASE
)

# Palavras que NAO podem aparecer no nome extraido (sinal de falso positivo -
# pegou continuacao de frase juridica, nao um nome de pessoa).
_PALAVRAS_PROIBIDAS_NO_NOME = {
    'DE', 'DA', 'DO', 'DOS', 'DAS', 'E', 'EM', 'PARA', 'COM', 'SEM', 'POR',
    'CAUSA', 'DIREITO', 'COMARCA', 'VARA', 'CIVEL', 'FEDERAL', 'TITULAR',
    'EXIGIDA', 'CONCESSAO', 'EFEITO', 'SUSPENSIVO', 'EMBARGOS', 'ATIVIDADE',
    'RURAL', 'MANUTENCAO', 'PROCESSO', 'JULGAMENTO', 'SENTENCA',
}


def _nome_parece_valido(nome: str) -> bool:
    palavras = nome.split()
    if len(palavras) < 2:
        return False
    if any(len(p) < 3 for p in palavras):
        return False
    sem_acento = unicodedata.normalize('NFD', nome.upper())
    sem_acento = ''.join(c for c in sem_acento if unicodedata.category(c) != 'Mn')
    palavras_normalizadas = sem_acento.split()
    if any(p in _PALAVRAS_PROIBIDAS_NO_NOME for p in palavras_normalizadas):
        return False
    return True


def extrair_magistrado(texto: str):
    """Extrai nome/cargo do magistrado do texto oficial da comunicacao, SE
    houver o rotulo padronizado "RELATOR(A):". NUNCA inventa e NUNCA tenta
    adivinhar a partir de mencoes soltas a "juizo"/"vara"/"comarca" - retorna
    None nesses casos. E' proposital registrar menos casos, mas nunca um
    magistrado errado.
    """
    if not texto:
        return None
    m = _PADRAO_RELATOR.search(texto)
    if not m:
        return None
    nome = re.sub(r'\s+', ' ', m.group('nome')).strip(' .,')
    if not _nome_parece_valido(nome):
        return None
    cargo = m.groupdict().get('cargo', '') or ''
    return {'nome': nome.title(), 'cargo': cargo.title()}


# Mapeia o slug da tese candidata (triagem_divida_rural.py) pro nome real da
# nota em BASE_CONHECIMENTO/00 - TEMAS/, senao o link [[...]] fica quebrado.
_TEMA_POR_TESE = {
    'prorrogacao': 'Sumula298-STJ-Prorrogacao-Rural',
    'descaracterizacao_mora': 'Tema28-STJ-Descaracterizacao-Mora',
    'revisional': 'Sumula286-Cedula-Guarda-Chuva',
}


def _slug(texto: str) -> str:
    nfd = unicodedata.normalize('NFD', texto)
    sem_acento = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    limpo = re.sub(r'[^A-Za-z0-9]+', '_', sem_acento).strip('_')
    return limpo or 'SEM_NOME'


def registrar_caso(resumo_djen: dict, item_triagem: dict):
    """Registra a nota de caso + atualiza a nota do magistrado (se
    identificado). Retorna o caminho da nota de caso criada/atualizada, ou
    None se nao houver dado suficiente (sem tese candidata e sem magistrado -
    nao vale a pena registrar ruido).
    """
    tese = item_triagem.get('tese_candidata')
    tema_nota = _TEMA_POR_TESE.get(tese)
    magistrado = extrair_magistrado(resumo_djen.get('texto') or '')

    if not tese and not magistrado:
        return None

    os.makedirs(PASTA_CASOS, exist_ok=True)
    processo = item_triagem.get('processo') or 'SEM_PROCESSO'
    caminho_caso = os.path.join(PASTA_CASOS, f'{_slug(processo)}.md')

    ja_existe = os.path.exists(caminho_caso)
    if not ja_existe:
        with open(caminho_caso, 'w', encoding='utf-8') as f:
            f.write(f"""---
processo: {processo}
cliente: {item_triagem.get('cliente') or ''}
tese: {f"[[{tema_nota}]]" if tema_nota else (tese or '')}
magistrado: {f"[[{magistrado['nome']}]]" if magistrado else ''}
tribunal: {resumo_djen.get('tribunal') or ''}
status: em andamento
registrado_em: {datetime.now().strftime('%Y-%m-%d')}
---

## Fatos-chave
- Tipo de ato: {item_triagem.get('tipo_ato') or ''}
- Providencia sinalizada: {item_triagem.get('providencia_cabivel') or ''}
- Prazo (calculo preliminar): {item_triagem.get('data_limite_preliminar') or 'nao identificado'}

## Trecho da comunicacao
{(resumo_djen.get('texto') or '')[:1500]}

## Prognostico registrado
[preencher via agente maldonado-jurimetria.md quando houver analise]

## Resultado real (apos decisao)
[preencher quando sair a decisao - vira dado real para calibrar o proximo prognostico]
""")

    if magistrado:
        pasta_mag = os.path.join(
            PASTA_MAGISTRADOS,
            'JUSTICA_FEDERAL' if _e_federal(resumo_djen.get('tribunal'), resumo_djen.get('orgao')) else 'TJRO',
        )
        os.makedirs(pasta_mag, exist_ok=True)
        caminho_mag = os.path.join(pasta_mag, f"{_slug(magistrado['nome'])}.md")
        if not os.path.exists(caminho_mag):
            with open(caminho_mag, 'w', encoding='utf-8') as f:
                f.write(f"""---
nome: {magistrado['nome']}
cargo: {magistrado['cargo']}
---

# {magistrado['nome']}

Perfil construido automaticamente a partir dos casos reais do escritorio
observados na triagem diaria. Nao ha dado de fonte externa (Jusbrasil/
Escavador/TJRO bloqueiam busca automatizada) - so o que o proprio fluxo do
escritorio registrou.

## Casos observados
""")
        with open(caminho_mag, 'a', encoding='utf-8') as f:
            linha = f"- [[{_slug(processo)}|{processo}]]"
            if tese:
                linha += f" — tese: [[{tese}]]"
            linha += f" — {datetime.now().strftime('%Y-%m-%d')}\n"
            f.write(linha)

    return caminho_caso


def atualizar_vault(resumos_djen: list, itens_triagem: list) -> dict:
    """Roda registrar_caso() para o lote inteiro. Retorna contagem de casos
    e magistrados novos/atualizados - para o relatorio da triagem informar.
    """
    casos_registrados = 0
    magistrados_identificados = 0
    for resumo, item in zip(resumos_djen, itens_triagem):
        caminho = registrar_caso(resumo, item)
        if caminho:
            casos_registrados += 1
        if extrair_magistrado(resumo.get('texto') or ''):
            magistrados_identificados += 1
    return {'casos_registrados': casos_registrados, 'magistrados_identificados': magistrados_identificados}
