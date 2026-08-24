"""
Config central da equipe - Maldonado Advogados

Preencher no onboarding. Nao hardcodar IDs em nenhum outro modulo -
todo codigo deve importar deste arquivo.
"""

# IDs de usuario no ADVBOX (Configuracoes > Usuarios, no painel ADVBOX do escritorio)
USUARIOS_ADVBOX = {
    "RESPONSAVEL": 93208,     # Renan Gomes Maldonado de Jesus (OAB/RO 5769)
    "OUTRO_ADVOGADO": 101621,  # Bruno Vinicius de Souza Faustino (OAB/RO 13021)
    "CONTROLADORIA": 120163,  # Juliana Ferreira Gusmao de Lara (gerente juridico)
}

# Campo 'from' default das tarefas criadas via /posts
USUARIO_PADRAO_TAREFAS = "RESPONSAVEL"

# OABs monitoradas na captura de intimacoes via DJEN/Comunica (CNJ)
# Formato: (numero, UF)
OABS_MONITORADAS = [
    ("5769", "RO"),   # Renan Gomes Maldonado de Jesus
    ("13021", "RO"),  # Bruno Vinicius de Souza Faustino
]

# E-mails da equipe para convite de eventos de prazo no Google Agenda
EMAILS_EQUIPE_AGENDA = [
    # "juliana@...",
    # "renan@...",
]
