# Mensagem Astral

Chatbot de astrologia em português brasileiro: motor astrológico (Kerykeion) +
base de conhecimento (RAG) + LLM, com avaliação de fine-tuning LoRA como etapa posterior.

> As interpretações são apresentadas como conhecimento astrológico, sem alegar comprovação científica.

## Arquitetura
1. **Motor astrológico** – calcula mapa (signos, planetas, casas, aspectos) → JSON.
2. **Base de conhecimento** – textos próprios/autorizados/domínio público, recuperados por RAG.
3. **LLM** – recebe o JSON + trechos recuperados e responde em português, sem inventar posições.

## Status
- [x] Etapa 1 – Configuração
- [x] Etapa 2 – Motor astrológico
- [~] Etapa 3 – Base de conhecimento (schema, validador e lote piloto de 12 signos aprovados; faltam planetas, casas e aspectos)
- [ ] Etapa 4 – MVP com RAG
- [ ] Etapa 5 – Fine-tuning (LoRA)
- [ ] Etapa 6 – Avaliação e documentação

## Como rodar (Colab)
Abra `notebooks/01_setup.ipynb` no Colab (File → Open → GitHub) e execute as células.
Detalhes em [`docs/workflow.md`](docs/workflow.md).

## Dados
Nenhum livro protegido, dado pessoal de nascimento, credencial ou modelo grande é versionado aqui. Ver `data/README.md`.
