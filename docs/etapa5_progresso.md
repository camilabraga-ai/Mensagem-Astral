# Etapa 5 — Trânsitos e mensagem diária (progresso)

Objetivo: mensagem diária personalizada relacionando os trânsitos do dia ao mapa natal.
Status geral: **em andamento** (não marcar como concluída sem confirmação da usuária).

## Arquitetura
```
mapa natal + data -> transit_positions (Kerykeion, meio-dia local) -> find_aspects (x Sol/Lua/Asc natais)
  -> select_transits (pontuação, top 3) -> retrieve_daily (KnowledgeBase.lookup)
  -> build_daily_prompt (+ mensagens recentes) -> LLM (Haiku) -> check_faithfulness -> cache por pessoa/dia
```

## Limitações da base para trânsitos
1. Não há textos de trânsito: usamos significado do planeta, do aspecto, do signo atual do planeta e do ponto natal.
2. Não há textos de casas em trânsito: a casa onde o trânsito cai não é usada (evita inventar).
3. O texto de cada aspecto é genérico (igual para qualquer planeta).

## Passos
- [x] 1. Cálculo de trânsitos e aspectos (`src/transits/calc.py`, `tests/test_transits_calc.py`)
- [x] 2. Seleção dos trânsitos relevantes (`src/transits/select.py`, `tests/test_transits_select.py`): pontuação = aspecto × planeta × ponto natal × orbe, top 3, mínimo 0,15; penalidade 0,6 para trânsitos já destacados nos dias recentes (variedade diária)
- [x] 3. Recuperação na base (`src/transits/retrieval.py`, `tests/test_transits_retrieval.py`): planeta, planeta no signo de hoje, aspecto, ponto natal e Lua do dia; nada inventado, faltas em `missing`
- [x] 4. Prompt diário, cache e pipeline (`src/transits/prompt.py`, `cache.py`, `daily.py`, `tests/test_transits_daily.py`): cache por pessoa+dia (+modelo e versão do prompt), mensagens recentes no prompt, checagem de fidelidade reaproveitada
- [x] 5. Notebook 05 (`notebooks/05_transitos.ipynb`), `docs/transitos.md` e README

Chamadas pagas: nenhuma feita nesta etapa até agora; todas desligadas por padrão.

## Pendente (depende da usuária)
- Rodar o notebook 05 no Colab e gerar mensagens reais (flag `CONFIRMO_CHAMADA_PAGA_DIARIA`); avaliar qualidade, tamanho e fidelidade.
- Confirmação para marcar a Etapa 5 como concluída.
