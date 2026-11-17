# Etapa 6 — Interface web e experiência do usuário (progresso)

Status: **implementada e testada localmente; aguardando revisão e confirmação da usuária** (não marcar como concluída sem confirmação). O aplicativo **não foi publicado**.

## Entregue
- `app/streamlit_app.py`: telas inicial, formulário, confirmação de local/horário e mensagem do dia.
- `src/app/validation.py`: validação do formulário e checagem de horário local (inexistente/ambíguo por horário de verão).
- `src/app/geo.py`: busca de cidades com candidatos, timeout e erros em português.
- `src/app/service.py`: cache em disco, chave da API (ambiente/Secrets), mapa natal, mensagem do dia, limite por sessão, erros amigáveis.
- `.streamlit/config.toml` (tema provisório), `requirements-app.txt`, `docs/app.md`.
- Testes: `tests/test_app_validation.py`, `tests/test_app_service.py`, `tests/test_app_ui.py` (AppTest, sem rede e sem API).

## Preservado
Motor astrológico, RAG, trânsitos, prompt editorial aprovado (`daily-3`) e os 224 textos: nenhum foi alterado.

## Chamadas pagas
Nenhuma foi feita nesta etapa. Todos os testes usam LLM simulado. Haiku 5.5 é o modelo padrão.

## Pendente
- Usuária rodar a interface localmente e avaliar visual e fluxo.
- Teste pago real, somente com autorização.
- Confirmação para marcar a Etapa 6 como concluída; decisões de publicação (ver `docs/app.md`).
