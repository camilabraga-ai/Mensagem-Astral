# Trânsitos e mensagem diária (Etapa 5)

```
mapa natal + data -> transit_positions (Kerykeion) -> find_aspects -> select_transits
  -> build_daily_context (KnowledgeBase.lookup) -> build_daily_prompt -> LLM -> check_faithfulness -> cache
```

| Módulo | Papel |
|---|---|
| `src/transits/calc.py` | Posições dos 10 planetas no dia (Kerykeion, **meio-dia no fuso do local de nascimento**) e aspectos (conjunção, sextil, quadratura, trígono, oposição) com Sol, Lua e Ascendente natais. |
| `src/transits/select.py` | Seleção dos 3 trânsitos mais relevantes por pontuação. |
| `src/transits/retrieval.py` | Documentos da base para os trânsitos escolhidos (sem criar documentos). |
| `src/transits/prompt.py` | Prompt diário: 70 a 100 palavras, até 2 parágrafos, tom pessoal e levemente poético, linguagem simples, reflexão ou sugestão prática integrada, sem aviso de leitura simbólica (esse aviso fica nos Termos de Uso e no onboarding). |
| `src/transits/cache.py` | Cache em arquivos JSON por pessoa e dia. |
| `src/transits/daily.py` | `daily_message(kb, chart, dia, llm, cache)`. |

## Critério de seleção
`pontuação = peso do aspecto × peso do planeta × peso do ponto natal × fator de orbe`

- Aspecto: conjunção e oposição 1,0; quadratura 0,9; trígono 0,7; sextil 0,5.
- Planeta em trânsito: Júpiter e Saturno 1,0; Marte, Urano e Plutão 0,9; Sol e Netuno 0,8; Lua e Vênus 0,7; Mercúrio 0,6.
- Ponto natal: Sol e Lua 1,0; Ascendente 0,9.
- Fator de orbe: 1,0 quando exato, cai linearmente até 0 no orbe máximo do planeta (Sol 5°; Lua, Marte, Júpiter e Saturno 4°; demais 3°).
- Pontuação mínima 0,15; no máximo 3 trânsitos.
- **Variedade:** trânsitos que foram destaque nos 2 dias anteriores (lidos do cache) têm a pontuação multiplicada por 0,6. Em testes com dois mapas de referência ao longo de 14 dias, a seleção mudou quase todos os dias (10 a 14 trânsitos distintos; apenas 1 dia de 13 repetiu exatamente a seleção da véspera).
- A **Lua do dia** (signo em que está hoje) entra sempre como contexto, o que dá variação diária mesmo sem trânsitos marcantes.

## Documentos recuperados por trânsito
Significado geral do planeta, o planeta no signo em que está hoje, o aspecto e o ponto natal no signo natal. A base de 224 documentos não foi alterada.

## Limitações
- Não há textos de trânsito na base: a mensagem combina blocos gerais (planeta, signo, aspecto, ponto natal).
- Não há textos de casas em trânsito; a casa natal em que o trânsito cai não é usada.
- Só trânsitos para Sol, Lua e Ascendente natais.
- A hora de referência é o meio-dia local; a Lua se move ~13° por dia, então aspectos lunares muito próximos podem mudar de orbe ao longo do dia. Não há distinção entre aspecto aplicando e separando.
- Trânsitos lentos (Saturno, Júpiter) podem aparecer em vários dias seguidos, pois duram semanas; a variedade vem da penalidade de repetição, da Lua do dia e das mensagens recentes enviadas no prompt.
- A checagem de fidelidade é um alerta por palavras (mesma do RAG natal).

## Cache e custo
- Chave: pessoa (hash do instante e local de nascimento) + data; vale para o mesmo modelo e a mesma `PROMPT_VERSION`.
- A mensagem só é regerada se mudar a data, o modelo, a versão do prompt, ou com `force=True`.
- Os arquivos ficam no Drive (`outputs/mensagens_diarias/`), nunca no GitHub, e não guardam os dados de nascimento em claro.
- Chamadas pagas desligadas por padrão (`CONFIRMO_CHAMADA_PAGA_DIARIA = False` no notebook 05).
