# Fluxo GitHub + Colab + Drive

| Onde | O que fica |
|------|-----------|
| GitHub | código (`src/`), notebooks sem outputs, configs, testes, docs |
| Drive (`MyDrive/MensagemAstral/`) | livros, datasets, checkpoints, adaptadores, outputs |
| Colab | execução; clona o repo em `/content/Mensagem-Astral` |

## Regras
- **Lógica reutilizável vive em `src/`**; notebooks só orquestram e mostram resultados.
- Edite `src/` no Mac (git normal) → no Colab, `git pull` (o notebook 01 faz isso).
- Notebooks: salvar no GitHub via *File → Save a copy in GitHub* (Colab remove
  nada sozinho; limpe outputs grandes antes) ou baixar o `.ipynb` e commitar no Mac.
- Token do GitHub (só se o repo for privado ou para push a partir do Colab):
  guardar em **Colab → 🔑 Secrets** com o nome `GITHUB_TOKEN`. Nunca em células.
