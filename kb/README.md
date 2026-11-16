# kb/ — Base de conhecimento astrológico (schema v2.0)

`documentos.jsonl`: um documento por linha, em pt-BR, usado pelo RAG (Etapa 4) e, no futuro, como origem
dos pares de fine-tuning. Formal: `src/data/schemas/documento.schema.json`.

| Campo | Descrição |
|---|---|
| `schema_version` | `"2.0"` |
| `id` | `<tipo>.<entidades>`, em inglês: `signo.aries`, `planeta_signo.sun.aries`, `casa.1`... |
| `tipo` | signo, planeta, casa, aspecto, elemento, planeta_signo, elemento_signo (+ modalidade, combinacao, conceito reservados) |
| `entidades` | em inglês, minúsculas: `signo` (aries…pisces), `planeta` (sun…pluto), `casa` (1–12), `aspecto` (conjunction, sextile, square, trine, opposition), `elemento` (ascendant, midheaven, north_node, south_node, chiron) |
| `titulo`, `texto` | conteúdo em português (80–300 palavras, autocontido) |
| `abordagem` | psicologica, tradicional, evolutiva, outra |
| `tags` | minúsculas, sem acento |
| `split_grupo` | igual ao `id`; usado para dividir treino/validação/teste sem vazamento |
| `hash_texto`, `n_palavras` | integridade (SHA-256 do texto normalizado; contagem) |

## Conteúdo (224 documentos)
| Tipo | Qtd |
|---|---|
| `signo` | 12 |
| `planeta` (Sol a Plutão) | 10 |
| `casa` | 12 |
| `aspecto` | 5 |
| `elemento` (Ascendente, Meio do Céu, Quíron, Nodo Norte, Nodo Sul) | 5 |
| `planeta_signo` (10 planetas × 12 signos) | 120 |
| `elemento_signo` (5 pontos × 12 signos) | 60 |

## Compatibilidade com o motor astrológico
O `chart.py` devolve signos e aspectos em português (`"Áries"`, `"trígono"`). `KnowledgeBase.lookup()` traduz
esses nomes (e `medium_coeli` → `midheaven`), então o resultado do mapa pode ser usado diretamente:

```python
kb.lookup(planeta="moon", signo="Gêmeos")     # -> planeta_signo.moon.gemini
kb.lookup(aspecto="trígono")                  # -> aspecto.trine
kb.lookup(elemento="medium_coeli", signo="Peixes")
```

Uso: `KnowledgeBase.load("kb")`, `.lookup(...)`, `.rag_records()` (`src/data/kb.py`).
Validação: `python -m pytest tests/test_kb.py`. Avisos de textos muito parecidos (Jaccard > 0,5) continuam ativos.

Origem e revisão dos textos: ver [`ORIGEM.md`](ORIGEM.md).
