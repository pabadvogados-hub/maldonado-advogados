# Custo por peça: o que mudou e como aplicar

## Por que a peça custava caro
1. **Todos os agentes rodavam no Opus**, o modelo mais caro.
2. **PDFs lidos direto pelo Claude**: cada página vai como imagem e texto. Um processo ou extrato
   grande pesa mais do que a peça inteira.
3. **O Word era montado escrevendo código a cada peça**, e texto de saída é o token mais caro.
4. **Sessões longas**: cada nova mensagem reenvia a conversa toda. Várias peças na mesma sessão
   fazem a quarta peça pagar pelas três anteriores.

## O que o patch faz
| Arquivo | Efeito |
|---|---|
| `.claude/settings.json` | Modelo padrão **Sonnet** e raciocínio limitado (`MAX_THINKING_TOKENS=8000`) |
| `.claude/agents/*.md` | Agentes passam de `opus` para `sonnet` |
| `.claude/hooks/pdf_guard.py` | Bloqueia a leitura de PDF com mais de 5 páginas e manda usar o texto extraído |
| `FERRAMENTAS/preparar_caso.py` | Extrai o texto dos PDFs no computador, de graça, em um `_CASO.md` enxuto |
| `FERRAMENTAS/gerar_docx.py` | Converte a peça em Markdown para .docx no timbrado, sem o Claude escrever código |
| `.claude/commands/peca.md` | Comando `/peca` com o fluxo econômico de ponta a ponta |
| `CLAUDE.md` | Regras de economia que o Claude segue em toda sessão |

## Como aplicar (uma vez, em cada computador)
```bash
git pull
pip install -r requirements.txt      # instala o pypdf
```
Coloque o timbrado em `DOCS_MODELOS/timbrado_modelo.docx` (só cabeçalho e rodapé).
Feche e abra o Claude Code na pasta do projeto para ele carregar as configurações novas.

## Como usar
```
/peca "C:/caminho/pasta do cliente" revisional
```
Depois de cada peça: `/cost` mostra quanto custou, e `/clear` limpa antes da próxima.
Caso muito complexo: `/model opus` só nessa sessão.

## Conferir a forma de cobrança
Se a variável `ANTHROPIC_API_KEY` estiver definida no computador, o Claude Code cobra **por uso
na API**, peça a peça. Com login por assinatura (Pro/Max, comando `/login`), o uso entra na
mensalidade. Para conferir: `/status` dentro do Claude Code mostra qual conta está em uso.
