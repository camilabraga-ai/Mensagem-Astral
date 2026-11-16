# kb/ — Base de conhecimento astrológico (schema v2.0)

`documentos.jsonl`: um documento por linha, em pt-BR, usado pelo RAG (Etapa 4) e, no futuro, como origem
dos pares de fine-tuning. Formal: `src/data/schemas/documento.schema.json`.

| Campo | Descrição |
|---|---|
| `schema_version` | `"2.0"` |
| `id` | `signo.aries`, `planeta.sol`... (derivado das entidades) |
| `tipo` | signo, planeta, casa, aspecto, elemento, modalidade, combinacao, conceito |
| `entidades` | chaves iguais às do mapa (`signo`, `planeta`, `planeta_2`, `casa`, `aspecto`) |
| `titulo`, `texto` | conteúdo (80–300 palavras, autocontido) |
| `abordagem` | psicologica, tradicional, evolutiva, outra |
| `tags` | minúsculas, sem acento |
| `split_grupo` | grupo para dividir treino/validação/teste sem vazamento |
| `hash_texto`, `n_palavras` | integridade (SHA-256 do texto normalizado; contagem) |

Uso: `KnowledgeBase.load("kb").lookup(signo="Áries")` e `.rag_records()` (`src/data/kb.py`).
Validação: `python -m pytest tests/test_kb.py`.

Origem e revisão dos textos: ver [`ORIGEM.md`](ORIGEM.md).
