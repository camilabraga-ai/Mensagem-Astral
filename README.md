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
- [x] Etapa 3 – Base de conhecimento (224 documentos: signos, planetas, casas, aspectos, pontos e combinações)
- [x] Etapa 4 – RAG (recuperação estruturada por metadados, geração com Claude Haiku 5.5, checagem de fidelidade; ver docs/rag.md)
- [x] Etapa 5 – Trânsitos e mensagem diária (trânsitos Kerykeion, seleção, RAG, Haiku 5.5, cache por pessoa/dia; ver docs/transitos.md)
- [ ] Fine-tuning (LoRA) – adiado
- [~] Etapa 6 – Interface web (Streamlit) (implementada e testada localmente; ver docs/app.md e docs/etapa6_progresso.md)
- [ ] Avaliação e documentação final

## Interface web
`pip install -r requirements-app.txt` e `streamlit run app/streamlit_app.py` (detalhes em [`docs/app.md`](docs/app.md)).

## Como rodar (Colab)
Abra `notebooks/01_setup.ipynb` no Colab (File → Open → GitHub) e execute as células.
Detalhes em [`docs/workflow.md`](docs/workflow.md).

## Dados
Nenhum livro protegido, dado pessoal de nascimento, credencial ou modelo grande é versionado aqui. Ver `data/README.md`.
