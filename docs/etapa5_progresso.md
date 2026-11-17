# Etapa 5 — Trânsitos e mensagem diária (progresso)

Objetivo: mensagem diária personalizada relacionando os trânsitos do dia ao mapa natal.
Status geral: **concluída** (confirmada pela usuária em 2026-11-16).

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

## Conclusão (2026-11-16)
- Pipeline completo validado com a API real (Claude Haiku 5.5): trânsitos, seleção, RAG, mensagem, cache e checagem de fidelidade.
- Cache confirmado no Colab: a segunda consulta do mesmo dia fez 0 chamadas à API.
- Testes: 264 no Mac (61 dos módulos de trânsitos também passaram no Colab).
- Formato e tom editorial **aprovados** e mantidos como padrão do projeto (`PROMPT_VERSION = "daily-3"`):
  70 a 100 palavras, até 2 parágrafos, tom natural, contemporâneo e conversacional, sem metáforas nem poesia,
  astrologia como base sem jargão técnico, uma observação e uma sugestão prática, sem autoajuda e
  **sem aviso de leitura simbólica no corpo da mensagem** (o aviso fica nos Termos de Uso e no onboarding).
- Custo observado: ~4,6 mil tokens de entrada e ~1,7 mil de saída por mensagem (≈ US$ 0,0013).
- Qualquer mudança no prompt exige alterar `PROMPT_VERSION`, o que invalida o cache.
- **Atualização (Etapa 6, `daily-6`):** a astrologia deixou de aparecer no texto. Ela é só o raciocínio interno (trânsitos
  e referências do RAG, inalterados); a mensagem trata de uma situação cotidiana concreta, com reflexão ou sugestão útil,
  sem nomes de planetas, signos, casas ou aspectos. Alerta (não bloqueia) `check_no_jargon` registra se algum termo escapar.
  As mensagens `daily-3` continuam guardadas: o cache agora usa `<data>.<versão>.json`, então uma versão nunca sobrescreve outra.

## Fora do escopo desta etapa (candidatos para o futuro)
- Trânsitos para outros pontos natais além de Sol, Lua e Ascendente.
- Textos de trânsito e de casas em trânsito na base.
- Distinção entre aspecto aplicando e separando.
- Desligar o raciocínio interno do modelo para reduzir custo (exige teste de qualidade).
- Fine-tuning (adiado).
