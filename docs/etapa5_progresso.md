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
- [ ] 2. Seleção dos trânsitos relevantes (`src/transits/select.py`)
- [ ] 3. Recuperação na base (`src/transits/retrieval.py`)
- [ ] 4. Prompt diário, geração e cache (`src/transits/prompt.py`, `cache.py`, `daily.py`)
- [ ] 5. Notebook 05, documentação e README

Chamadas pagas: nenhuma feita nesta etapa até agora; todas desligadas por padrão.
