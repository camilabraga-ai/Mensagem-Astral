# RAG (Etapa 4)

```
dados de nascimento -> calculate_chart (Kerykeion) -> retrieve (KnowledgeBase.lookup)
                    -> build_prompt -> LLM (AnthropicLLM) -> check_faithfulness -> AstralMessage
```

| Módulo | Papel |
|---|---|
| `src/rag/retriever.py` | Posicionamentos calculados (Sol, Lua, Ascendente) e aspectos entre eles -> documentos da base, por metadados. Sem embeddings. |
| `src/rag/prompt.py` | Prompt de sistema (regras) + prompt de usuário (dados calculados + interpretações recuperadas). |
| `src/rag/generator.py` | `AnthropicLLM` (API), `generate_message`, `message_from_birth` e `check_faithfulness`. |

Documentos recuperados por ponto: combinação (`planeta_signo` / `elemento_signo`), significado geral do ponto, casa (Sol e Lua), signos envolvidos, e aspectos calculados entre os três pontos.

**Fidelidade:** `check_faithfulness` avisa quando a mensagem cita signo, planeta/ponto, aspecto ou casa que não esteja nos dados calculados nem nos textos recuperados. É um alerta, não bloqueia.

**Modelo:** padrão `claude-haiku-5-5` (menor custo), definido em `DEFAULT_MODEL` (`src/rag/generator.py`). Para trocar: `AnthropicLLM(model="claude-opus-5-5")`; nada mais depende do modelo.

**Custo:** apenas `AnthropicLLM.complete` chama a API (paga). Testes usam LLM e cliente simulados. O notebook 04 deixa a chamada desligada por padrão (`CONFIRMO_CHAMADA_PAGA = False`).

**Privacidade:** o prompt contém signos, graus e casas, e os textos da base. Data, hora e cidade de nascimento não são enviadas.

**Consumo e teste com vários mapas:** `AnthropicLLM` registra os tokens de cada chamada (`last_usage`, `total_usage`) e `generate_message` devolve `usage`. A seção 8 do notebook 04 gera mensagens para uma lista de mapas guardada só no Drive (`outputs/mapas_teste.json`), com flag própria desligada por padrão.

## Resultados do primeiro teste real (2026-11-16)

Modelo `claude-haiku-5-5`, effort `low`. Primeira rodada: 1 mapa (primeiro teste, `max_tokens=2000`) e 3 mapas na seção 8 do notebook 04. Os dados de nascimento e as mensagens geradas **não** são registrados aqui.

| Item | Resultado |
|---|---|
| Fidelidade aos dados calculados | Todas as mensagens citaram só Sol, Lua, Ascendente, casas e aspectos calculados, conferidos manualmente |
| Mapa sem aspecto entre os três pontos | Nenhum aspecto inventado |
| Aspecto novo (quadratura) | Usado corretamente |
| Avisos de `check_faithfulness` | 1 falso positivo ("simples oposição", sentido comum), corrigido; depois, nenhum aviso |
| Tamanho das mensagens | 330 a 400 palavras (pedido: 250 a 350) |
| Tokens por mensagem | ~5.200 de entrada e ~1.900 de saída (texto visível ~700; o resto é raciocínio interno) |
| Custo | ~US$ 0,0015 por mensagem (3 mensagens: US$ 0,0044) |

**Ajuste feito:** a saída chegou a 1.970 tokens com `max_tokens=2000`, perto do corte. O padrão passou para 4000.

### Segunda rodada: reforço contra cópia de frases da base

O prompt de sistema passou a orientar que os textos de referência sejam usados "como fonte de ideias, não como texto". Mesmos 3 mapas, mesmo modelo.

| Item | Antes do reforço | Depois |
|---|---|---|
| Fidelidade aos dados calculados | conferida, sem invenções | conferida, sem invenções |
| Avisos de `check_faithfulness` | 0 (após correção do falso positivo) | 0 |
| Frases reaproveitadas da base (Ascendente em Aquário: "diferença significativa… oposição") | presentes | ausentes (reescritas com outras palavras) |
| Tokens de saída por mensagem | 1.781 / 1.970 / 1.913 | 830 / 1.291 / 1.587 |
| Custo das 3 mensagens | US$ 0,0044 | US$ 0,0034 |
| Estilo | texto mais entrelaçado | abertura integradora, um parágrafo por ponto do mapa e fecho; um pouco mais estruturado |

## Limitações conhecidas
- Considera só Sol, Lua e Ascendente (outros planetas, Meio do Céu, nodos e Quíron existem na base, mas não são usados na mensagem).
- Gera uma mensagem por mapa; não responde perguntas nem mantém conversa.
- `check_faithfulness` é um alerta por palavras, não uma verificação semântica: uma invenção sem citar o nome de um planeta ou signo não é detectada.
- A mensagem pode reaproveitar expressões dos textos da base. O reforço no prompt eliminou o caso observado, mas não há medição automática de cópia.
- A busca de endereços usa um serviço gratuito (Nominatim): um erro de digitação na cidade pode resolver para outro lugar sem aviso.
- Avaliação feita com 4 mapas e leitura manual; não há métrica automática de qualidade.
