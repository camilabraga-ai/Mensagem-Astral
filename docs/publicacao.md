# Publicação e manutenção (Streamlit Community Cloud)

App publicado em **https://mensagem-astral.streamlit.app/** (público, sem login), a partir de `camilabraga-ai/Mensagem-Astral`, branch `main`, arquivo `app/streamlit_app.py`, Python 3.13. Repositório **privado**.

## Como foi publicado (procedimento)
1. `share.streamlit.io` → entrar com GitHub (conta dona do repositório) → autorizar acesso a repositórios privados.
2. **Create app → Deploy a public app from GitHub**: repositório `camilabraga-ai/Mensagem-Astral`, branch `main`, **Main file path `app/streamlit_app.py`** (não `streamlit_app.py`), URL `mensagem-astral`.
3. **Advanced settings**: Python **3.13**; Secrets (TOML):
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   CACHE_SALT = "<texto aleatório longo: python3 -c 'import secrets; print(secrets.token_urlsafe(32))'>"
   MAX_DAILY_GENERATIONS = "40"
   MAX_HOURLY_GENERATIONS = "12"
   ```
4. **Deploy.** A Cloud lê `app/requirements.txt` (o `requirements.txt` da raiz é só do Colab) e instala em alguns minutos.
5. **Atenção:** apps vindos de repositório privado nascem com acesso restrito. Em **⋮ → Settings → Sharing** marcar **"This app is public and searchable"** e salvar. Sem isso, quem abre o link vê "You do not have access to this app".
6. Apagar qualquer cópia local dos Secrets (ex.: `.streamlit/secrets.cloud.toml`).

## Validação feita no app publicado (2026-11-17)
- Tela inicial no desktop e no celular, botão principal visível sem rolar, bloco "Privacidade e termos de uso".
- Entradas inválidas: formulário vazio e cidade inexistente mostram avisos em português.
- Fluxo completo com uma chamada real ao Haiku: mensagem de 84 palavras em 2 parágrafos, sem termos astrológicos, sem erros; "Seu mapa" e "Começar de novo" visíveis.
- Mesma pessoa em nova sessão (celular): a mesma mensagem veio do cache, sem botão de gerar.
- Testado pela usuária em celular real: tudo certo. Safari não foi testado (ficou como limitação).

## Manutenção
| Tarefa | Como |
|---|---|
| Atualizar o app | `git push` na `main`: a Cloud reinicia sozinha (cache e contador do dia voltam a zero) |
| Pausar toda geração nova | Secrets: `GENERATION_ENABLED = "false"` (mensagens já guardadas continuam aparecendo). Alterações levam cerca de 1 minuto |
| Mudar limites | Secrets: `MAX_DAILY_GENERATIONS`, `MAX_HOURLY_GENERATIONS` |
| Trocar a chave da Anthropic | Gerar nova no console, atualizar `ANTHROPIC_API_KEY` nos Secrets e revogar a antiga |
| Trocar o sal do cache | Secrets: `CACHE_SALT` (descarta o cache existente) |
| Se houver abuso | Pausar a geração; se preciso, **Settings → Sharing → Only specific people can view this app** |
| Ver logs / reiniciar | Painel do app → Manage app (logs) e ⋮ → Reboot app |
| Custos | Limites internos (40/dia, 12/h) + limite de gastos no console da Anthropic (já configurado) |

## Comportamentos da hospedagem a ter em mente
- Apps sem tráfego por 12 h entram em repouso; quem abrir o link clica para acordar. Cache e contador locais podem ser perdidos.
- Um selo "Hosted with Streamlit" aparece no canto inferior direito (é da plataforma; no celular pode sobrepor o rodapé).
- O link público pode ser indexado por buscadores: compartilhe só com o grupo de teste.
