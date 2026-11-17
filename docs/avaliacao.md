# Avaliação do sistema

Este documento separa o que foi **medido**, o que é **estimativa** e o que **não foi avaliado**. Data da última execução
dos testes: 2026-11-17 (Python 3.13, macOS; também em ambiente virgem criado só com `app/requirements.txt` + pytest).

## 1. Estratégia de testes automatizados
Todos os testes rodam **offline, sem custo e sem chaves**: o LLM é simulado e a busca de cidades é substituída por dados
fixos. A API paga só foi chamada manualmente, com autorização explícita a cada vez (seção 5).

| Camada | Arquivo | Testes | O que cobre |
|---|---|---:|---|
| Motor astrológico | `test_astrology.py` | 7 | estrutura do mapa, UTC e horário de verão, Sol em J2000, signo × longitude, JSON, mapa de referência (ver 3) |
| Base de conhecimento | `test_kb.py` | 21 | schema, hash, nº de palavras, IDs, cobertura, similaridade, vazamento treino/validação |
| Recuperação (mapa natal) | `test_rag_retriever.py` | 152 | documentos esperados, sem repetição, sem casa para o Ascendente, 144 combinações signo × casa sem lacunas |
| Geração e fidelidade | `test_rag_generator.py` | 19 | prompt, cliente Anthropic simulado, recusa/truncamento, checagem de fidelidade, registro de tokens |
| Trânsitos (cálculo) | `test_transits_calc.py` | 17 | posições, Lua ≈ 13°/dia, determinismo, virada de 360°, cada aspecto, orbes |
| Trânsitos (seleção) | `test_transits_select.py` | 11 | fórmula documentada, ordenação, desempate, penalidade de repetição |
| Trânsitos (recuperação) | `test_transits_retrieval.py` | 7 | blocos por trânsito, faltas registradas sem inventar |
| Mensagem diária | `test_transits_daily.py` | 38 | pipeline, cache por pessoa/dia/versão, prompt editorial, alerta de jargão |
| Limites e cache | `test_app_limits.py` | 31 | limite diário/horário, concorrência, chave de emergência, sal do cache, isolamento entre pessoas |
| Serviço do app | `test_app_service.py` | 36 | mapa a partir do formulário, trava por pessoa/dia, erros amigáveis, privacidade do prompt |
| Validação de formulário | `test_app_validation.py` | 25 | datas, horário inexistente/ambíguo de verão, limites de tamanho |
| Interface | `test_app_ui.py` | 36 | fluxo completo com `AppTest`, retry, limites, pausa, textos de privacidade |
| Visual | `test_app_visual.py` | 26 | CSS e SVG (ex.: regressão do corte do cartão "Seu mapa") |
| Publicação | `test_deploy_config.py` | 7 | dependências cobrem os imports, varredura de segredos, arquivos estáticos |
| Estrutura | `test_structure.py` | 4 | pacotes e arquivos esperados |
| **Total** | | **437** | **437 passaram, 0 falharam** |

Os 152 testes da recuperação incluem 144 gerados por parametrização (12 signos × 12 casas).

## 2. Cobertura e o que os testes não provam
Não há medição de cobertura de código (`pytest-cov` não está configurado): **pendência**. Não há testes de carga, de
integração com o Nominatim real nem de execução em navegadores além do Chrome.

## 3. Validação do cálculo astrológico
- **Fatos astronômicos:** em 2000-01-01 12:00 UTC a longitude do Sol é ≈ 280,4° (Capricórnio) — teste com tolerância de 0,3°.
- **Consistência interna:** o signo de cada planeta bate com `longitude // 30`; a conversão local → UTC foi testada com e sem
  horário de verão histórico (São Paulo, 1991).
- **Comparação com fonte externa:** `test_mapa_de_referencia_local` compara signo, grau e retrogradação de todos os pontos
  de um mapa conferido manualmente em um site de astrologia. O arquivo de referência é **dado pessoal, está no
  `.gitignore` e não é versionado**; por isso o teste só é executado na máquina da autora (nas demais, é ignorado). O
  nome do site usado na conferência não ficou registrado no repositório. **Esta validação, portanto, não é reproduzível
  por terceiros** (pendência: criar mapas de referência com dados fictícios ou de figuras públicas).
- **Trânsitos:** posições dos 10 planetas, movimento lunar (~13°/dia), determinismo e cada tipo de aspecto
  (parametrizado) têm teste. A convenção "meio-dia no fuso do local de nascimento" é uma decisão, não uma medida.

## 4. Validação da recuperação de documentos
- **Cobertura da base:** teste confere 12 signos, 10 planetas × 12 signos, 5 pontos × 12 signos e 12 casas (224 documentos,
  contagem por tipo verificada).
- **Recuperação sem lacunas:** 144 combinações signo × casa para Sol, Lua e Ascendente retornam `missing == []`.
- **Correção:** o teste de recuperação confere os IDs esperados (ex.: `planeta_signo.sun.<signo>`), ausência de duplicatas e
  que só os pontos pedidos entram.
- **Integridade dos textos:** SHA-256 por documento, contagem de palavras (80–300 sugerido; média real 123, mín. 86, máx.
  168), alerta de similaridade (Jaccard de 6-gramas > 0,5) e proibição de vazamento entre divisões treino/validação.
- **Não avaliado:** não existe conjunto de perguntas com respostas esperadas, então **não há métricas de recuperação**
  (precisão, recall, MRR). Como a recuperação é por chave exata, o que se mede é cobertura, não relevância semântica.
  Também não houve comparação com embeddings.

## 5. Avaliação da geração de mensagens
Feita por **leitura manual e checagens automáticas simples**; não há avaliação automática de qualidade.

**Mapa natal (Etapa 4, 2026-11-16, ver [`rag.md`](rag.md)):** 4 mapas, 2 rodadas. Todas as mensagens citaram apenas pontos
calculados (conferido manualmente); mapa sem aspecto não recebeu aspecto inventado; 1 falso positivo da checagem foi
corrigido; reforço contra cópia de frases da base eliminou o caso observado (sem medição automática de cópia).

**Mensagem diária (Etapas 5 e 6):** o tom editorial foi revisado e aprovado pela autora por leitura. O `daily-6` foi
verificado em 3 mapas distintos após a autora notar mensagens parecidas entre mapas diferentes nas versões `daily-4`/`daily-5`
(os exemplos no prompt eram copiados pelo modelo; foram removidos). O app publicado foi validado com **uma** mensagem real.

Checagens automáticas disponíveis em cada mensagem (não bloqueiam):
- `check_faithfulness`: termos astrológicos fora do que foi calculado ou recuperado (por palavras, não semântica);
- `check_no_jargon`: planetas, signos, casas ou aspectos que escaparam para o texto final.

Nas **9 mensagens reais guardadas no cache local** (`daily-3` a `daily-6`) ambos os alertas ficaram em **0**.

## 6. Métricas disponíveis
Fonte: registros de `usage` guardados no cache local (a pasta `.cache/` não é versionada). **Amostra pequena (9 mensagens
reais, 3 por versão no máximo); não é benchmark.**

| Versão do prompt | n | Palavras | Tokens de entrada | Tokens de saída |
|---|---:|---|---|---|
| `daily-3` | 3 | 95, 86, 85 | 5.668 / 4.285 / 2.986 | 240 / 1.532 / 1.162 |
| `daily-4` | 1 | 103 | 4.525 | 231 |
| `daily-5` | 2 | 96, 83 | 6.130 / 4.699 | 212 / 1.108 |
| `daily-6` (atual) | 3 | 92, 85, 83 | 6.293 / 4.910 / 3.611 | 1.279 / 906 / 1.727 |

- Média das 3 mensagens `daily-6`: ≈ 4.938 tokens de entrada e ≈ 1.304 de saída.
- Os tokens de saída incluem o raciocínio interno do modelo (o texto visível tem ~100 palavras); a variação de 212 a 1.727
  indica que o consumo de saída é bem irregular.
- Mensagem natal (Etapa 4): ≈ 5.200 de entrada e 830 a 1.970 de saída; texto de 330–400 palavras (pedido: 250–350).
- **Cumprimento do limite de palavras:** `daily-6` ficou dentro de 70–100 nas 3 amostras; `daily-4` (103) passou do limite,
  o que motivou o ajuste.

## 7. Latência
**Não medida.** O código não registra tempo de resposta e nenhuma medição de latência foi guardada. O cliente usa timeout de
60 s e 2 novas tentativas. **Pendência:** instrumentar a chamada (p50/p95) e medir no app publicado.

## 8. Custo por mensagem
**Estimativa, não medição de fatura.** Premissas:
- tokens medidos na seção 6;
- preço **assumido** de US$ 0,10 por milhão de tokens de entrada e US$ 0,50 por milhão de saída para o `claude-haiku-5-5`,
  valor que está na constante `PRECO_POR_MTOK` do `notebooks/04_rag.ipynb` (com o comentário "confira o preço atual"; o preço
  não foi reconferido nesta revisão);
- sem cache de prompt e sem desconto de lote.

| Cálculo | Resultado |
|---|---|
| `daily-6`, média (4.938 entrada, 1.304 saída) | ≈ US$ 0,00049 + US$ 0,00065 ≈ **US$ 0,0011** |
| Faixa nas 9 amostras | ≈ US$ 0,0004 a US$ 0,0015 |
| Etapa 4 (mapa natal, 3 mensagens, 2ª rodada) | US$ 0,0034 no total, ≈ US$ 0,0011 cada (registrado em `rag.md`) |
| Teto de segurança usado no app | US$ 0,003 por mensagem × 40 por dia ≈ **US$ 0,12/dia** (margem conservadora, não medida) |

Cache hit custa zero. A fatura real da Anthropic não foi usada para conferir estas estimativas (**pendência**).

## 9. Limitações da avaliação atual
- Amostras muito pequenas (3 a 4 mapas; 9 mensagens com tokens registrados) e avaliação por uma única pessoa.
- Qualidade textual sem métrica automática, sem rubrica pontuada, sem LLM-as-judge e sem avaliação cega por terceiros.
- Fidelidade verificada por palavras-chave; invenções que não citam nome de planeta ou signo não seriam detectadas.
- Diversidade entre mapas foi verificada por leitura; não há medida de similaridade entre mensagens.
- Sem latência, sem cobertura de código, sem teste de carga, sem teste em Safari.
- Resultados de tokens e palavras vêm de um cache local não versionado, portanto outra pessoa não consegue reproduzi-los
  sem refazer chamadas pagas.

## 10. Pendências de avaliação (ordenadas por valor para o portfólio)
1. Conjunto de avaliação fixo (ex.: 20 mapas fictícios × alguns dias) com rubrica e/ou LLM-as-judge, guardando as saídas.
2. Medir latência (p50/p95) e tokens em lote, registrando em arquivo versionável.
3. Mapas de referência com dados fictícios ou públicos, validados em fonte externa citada.
4. Cobertura de código (`pytest-cov`).
5. Métrica de similaridade entre mensagens de mapas diferentes e do mesmo mapa em dias seguidos.
6. Conferir o custo estimado com a fatura da Anthropic.
7. Experimento comparando recuperação por metadados com embeddings (só se houver hipótese de ganho).
