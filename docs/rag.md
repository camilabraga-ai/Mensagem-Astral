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
