# -*- coding: utf-8 -*-
"""
Triagem de Controladoria - Maldonado Advogados
================================================
Classificador de 1a passada para intimacoes/publicacoes do DJEN, aplicado ao
nicho do escritorio (divida rural bancaria). Faz o trabalho MECANICO
(extrair tipo de ato, calcular prazo preliminar, sinalizar candidata a tese)
via regex/palavra-chave - e' rapido e 100% auditavel, mas e' so a 1a passada.

Casos ambiguos (o classificador nao tem certeza, ou o texto e' complexo) sao
sinalizados como "REVISAO_MANUAL" e devem ser colados no agente Claude
`.claude/agents/maldonado-controladoria.md` para leitura fina - o classificador
NUNCA decide sozinho qual das 3 teses cabe quando o texto for ambiguo (mesma
regra de ouro do agente).

Nao protocola, nao cria tarefa - so classifica. A criacao de tarefa no ADVBOX
e feita por quem chama este modulo (OPERACIONAL/main.py, comando `triagem`),
sempre com confirmacao explicita.
"""
import re
from datetime import datetime, timedelta


# ============================================================
# 1. TIPO DE ATO (a partir do campo tipoComunicacao + texto)
# ============================================================

_PALAVRAS_SENTENCA = ("sentença", "sentenca", "julgo", "julgamento antecipado")
_PALAVRAS_DECISAO = ("decisão", "decisao", "indefiro", "defiro", "tutela de urgência",
                      "tutela de urgencia", "agravo de instrumento")
_PALAVRAS_AUDIENCIA = ("audiência", "audiencia", "designo audiência", "designo audiencia")
_PALAVRAS_CIENCIA = ("ciência", "ciencia", "dar-se ciência", "tomar ciência",
                      "arquivamento", "baixa definitiva")
_PALAVRAS_PRAZO = ("prazo de", "manifeste-se", "intime-se para", "no prazo",
                    "apresente", "junte", "cumpra")


def classificar_tipo_ato(texto: str, tipo_comunicacao: str = "") -> str:
    """Classifica o ato em uma categoria ampla, a partir de palavras-chave.

    Retorna uma das strings: 'sentenca', 'decisao', 'audiencia',
    'intimacao_com_prazo', 'ciencia', 'indefinido'.
    """
    t = (texto or "").lower()
    tc = (tipo_comunicacao or "").lower()
    junto = f"{tc} {t}"

    if any(p in junto for p in _PALAVRAS_SENTENCA):
        return "sentenca"
    if any(p in junto for p in _PALAVRAS_AUDIENCIA):
        return "audiencia"
    if any(p in junto for p in _PALAVRAS_DECISAO):
        return "decisao"
    if any(p in junto for p in _PALAVRAS_PRAZO):
        return "intimacao_com_prazo"
    if any(p in junto for p in _PALAVRAS_CIENCIA):
        return "ciencia"
    return "indefinido"


# ============================================================
# 2. PRAZO (extração de "N dias" do texto + cálculo preliminar)
# ============================================================

_REGEX_PRAZO_DIAS = re.compile(r"prazo\s+de\s+(\d{1,3})\s*\(?[a-z]*\)?\s*dias", re.IGNORECASE)


def extrair_prazo_dias(texto: str):
    """Tenta extrair o numero de dias do prazo citado no texto. Retorna int ou None."""
    if not texto:
        return None
    m = _REGEX_PRAZO_DIAS.search(texto)
    return int(m.group(1)) if m else None


def calcular_data_limite(data_disponibilizacao: str, dias: int, dias_uteis: bool = True):
    """Calcula uma data-limite PRELIMINAR a partir da data de disponibilizacao.

    ATENCAO: e' um calculo aproximado (so pula sabado/domingo quando
    dias_uteis=True; nao considera feriados forenses nem o inicio de contagem
    no 1o dia util seguinte). Sempre rotular como "preliminar, sujeito a
    conferencia" na saida - nunca apresentar como definitivo.
    """
    if not data_disponibilizacao or not dias:
        return None
    try:
        data = datetime.strptime(data_disponibilizacao[:10], "%Y-%m-%d")
    except ValueError:
        return None

    if not dias_uteis:
        return (data + timedelta(days=dias)).strftime("%Y-%m-%d")

    restantes = dias
    while restantes > 0:
        data += timedelta(days=1)
        if data.weekday() < 5:  # 0-4 = seg-sex
            restantes -= 1
    return data.strftime("%Y-%m-%d")


# ============================================================
# 3. TESE DE DÍVIDA RURAL (candidata, via palavra-chave — 1a passada)
# ============================================================

_PALAVRAS_PRORROGACAO = ("prorrogação", "prorrogacao", "alongamento", "cédula de crédito rural",
                          "cedula de credito rural", "cpr", "manual de crédito rural", "súmula 298",
                          "sumula 298")
_PALAVRAS_MORA = ("descaracterização da mora", "descaracterizacao da mora", "tema 28",
                   "declaratória", "declaratoria")
_PALAVRAS_REVISIONAL = ("ação revisional", "acao revisional", "revisão de contrato",
                         "revisao de contrato", "capitalização", "capitalizacao",
                         "juros abusivos", "súmula 539", "sumula 539", "súmula 541", "sumula 541")


def classificar_tese_candidata(texto: str):
    """1a passada por palavra-chave. Retorna uma tupla (tese, confianca).

    tese: 'prorrogacao' | 'descaracterizacao_mora' | 'revisional' | None
    confianca: 'baixa' (so 1 sinal fraco) | 'media' (varios sinais) — NUNCA 'alta':
      confirmação definitiva da tese fica para leitura humana/IA fina, nunca
      só para o classificador mecânico (mesmo guard-rail do agente
      maldonado-divida-rural.md: nunca escolher a tese sozinho em caso ambíguo).
    """
    t = (texto or "").lower()
    pontos = {
        "prorrogacao": sum(1 for p in _PALAVRAS_PRORROGACAO if p in t),
        "descaracterizacao_mora": sum(1 for p in _PALAVRAS_MORA if p in t),
        "revisional": sum(1 for p in _PALAVRAS_REVISIONAL if p in t),
    }
    tese, pts = max(pontos.items(), key=lambda kv: kv[1])
    if pts == 0:
        return None, None
    confianca = "media" if pts >= 2 else "baixa"
    return tese, confianca


_PECA_POR_TESE = {
    "prorrogacao": "Ação de prorrogação compulsória de contratos rurais c/c tutela cautelar antecedente",
    "descaracterizacao_mora": "Ação declaratória de descaracterização de mora (Tema 28/STJ)",
    "revisional": "Ação revisional de contrato bancário rural c/c tutela de urgência",
}


# ============================================================
# 4. MONTAGEM DO ITEM DE TRIAGEM (saída padrão)
# ============================================================

def montar_item_triagem(resumo_djen: dict, lawsuit_advbox: dict = None) -> dict:
    """Combina um item resumido do DJEN (ver comunica_djen.resumir) com o
    processo correspondente no ADVBOX (se encontrado) e devolve o bloco de
    triagem no formato descrito em .claude/agents/maldonado-controladoria.md.
    """
    texto = resumo_djen.get("texto", "")
    tipo_ato = classificar_tipo_ato(texto, resumo_djen.get("tipo", ""))
    tese, confianca = classificar_tese_candidata(texto)
    dias_prazo = extrair_prazo_dias(texto)
    data_limite = calcular_data_limite(resumo_djen.get("data"), dias_prazo) if dias_prazo else None

    if tipo_ato == "ciencia":
        providencia = "apenas ciencia"
        prioridade = "baixa"
        peca = None
    elif tipo_ato == "audiencia":
        providencia = "preparar audiencia"
        prioridade = "alta"
        peca = None
    elif tipo_ato in ("sentenca", "decisao", "intimacao_com_prazo"):
        providencia = "REVISAO_MANUAL - ato com prazo/mérito, confirmar peça e prazo"
        prioridade = "alta" if data_limite else "media"
        peca = _PECA_POR_TESE.get(tese) if tese else None
    else:
        providencia = "REVISAO_MANUAL - tipo de ato nao identificado pelo classificador"
        prioridade = "media"
        peca = None

    cliente = None
    responsavel = None
    if lawsuit_advbox:
        clientes = lawsuit_advbox.get("customers") or []
        cliente = clientes[0].get("name") if clientes else None
        responsavel = lawsuit_advbox.get("responsible")

    return {
        "processo": resumo_djen.get("processo"),
        "cliente": cliente or "NAO ENCONTRADO NO ADVBOX - conferir numero do processo",
        "responsavel_advbox": responsavel,
        "tribunal": resumo_djen.get("tribunal"),
        "orgao": resumo_djen.get("orgao"),
        "tipo_ato": tipo_ato,
        "providencia_cabivel": providencia,
        "tese_candidata": tese,
        "confianca_tese": confianca,
        "peca_necessaria": peca,
        "prazo_dias_extraido": dias_prazo,
        "data_limite_preliminar": data_limite,
        "prioridade": prioridade,
        "link_djen": resumo_djen.get("link"),
        "trecho": (texto or "")[:300],
    }


def triagem_lote(resumos_djen: list, lawsuits_por_processo: dict = None) -> list:
    """Aplica montar_item_triagem em lote. lawsuits_por_processo: dict
    {numero_processo_normalizado: lawsuit_dict} vindo do ADVBOX (opcional).
    """
    lawsuits_por_processo = lawsuits_por_processo or {}
    itens = []
    for r in resumos_djen:
        proc_norm = "".join(filter(str.isdigit, r.get("processo") or ""))
        lawsuit = lawsuits_por_processo.get(proc_norm)
        itens.append(montar_item_triagem(r, lawsuit))
    return itens


def imprimir_triagem(itens: list):
    if not itens:
        print("Nenhum item para triagem no periodo informado.")
        return

    prioridades = {"alta": 0, "media": 0, "baixa": 0}
    revisao_manual = 0
    precisam_peca = 0

    print(f"\n{'='*80}\n  TRIAGEM DE CONTROLADORIA — {len(itens)} item(ns)\n{'='*80}")
    for it in sorted(itens, key=lambda x: {"alta": 0, "media": 1, "baixa": 2}.get(x["prioridade"], 1)):
        prioridades[it["prioridade"]] = prioridades.get(it["prioridade"], 0) + 1
        if "REVISAO_MANUAL" in (it["providencia_cabivel"] or ""):
            revisao_manual += 1
        if it["peca_necessaria"]:
            precisam_peca += 1

        print(f"\nPROCESSO: {it['processo']}")
        print(f"CLIENTE: {it['cliente']}")
        print(f"TIPO DE ATO: {it['tipo_ato']}")
        print(f"PROVIDENCIA CABIVEL: {it['providencia_cabivel']}")
        if it["tese_candidata"]:
            print(f"TESE CANDIDATA: {it['tese_candidata']} (confianca: {it['confianca_tese']})")
        print(f"PECA NECESSARIA: {it['peca_necessaria'] or '-'}")
        if it["data_limite_preliminar"]:
            print(f"PRAZO (calculo preliminar, conferir): {it['data_limite_preliminar']}")
        print(f"PRIORIDADE: {it['prioridade']}")
        print(f"LINK DJEN: {it['link_djen']}")
        if it["trecho"]:
            print(f"TRECHO: {it['trecho']}...")

    print(f"\n{'='*80}")
    print(f"  RESUMO: {prioridades['alta']} alta | {prioridades['media']} media | {prioridades['baixa']} baixa")
    print(f"  {revisao_manual} item(ns) marcados p/ REVISAO_MANUAL (colar no agente maldonado-controladoria)")
    print(f"  {precisam_peca} item(ns) com peca candidata identificada")
    print(f"{'='*80}\n")
