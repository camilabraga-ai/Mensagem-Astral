# Etapa 7 — Preparação e publicação do MVP (progresso)

Status: **Fase 1 (preparação) concluída e aprovada em 2026-11-17.** Fase 2 (publicação) **não iniciada**: o app ainda não foi publicado e só será publicado com autorização expressa da usuária. A Etapa 7 não está concluída.

**Decisão da usuária (2026-11-17), que substitui a recomendação de app privado:** publicar como **aplicativo público no Streamlit Community Cloud, sem login nem autenticação**, compartilhando o link inicialmente com um pequeno grupo para testar o MVP. Mantidos: repositório GitHub privado, chave da Anthropic nos Secrets, limites internos de 40 mensagens/dia e 12/hora, cache e proteções, interface e funcionalidades aprovadas. A usuária já tem um limite de gastos configurado no console da Anthropic.

Restrições mantidas: design aprovado, prompt editorial (`daily-6`), RAG, motor astrológico e os 224 textos **não foram alterados**; nenhum login nem banco de dados foi adicionado; nenhuma chamada paga foi feita nesta fase (todos os testes usam LLM simulado).

## Riscos encontrados e o que foi feito
| # | Risco | Gravidade | Ação | Situação |
|---|---|---|---|---|
| 1 | `requirements.txt` da raiz não instala o app (só pandas, numpy, pytest, pyyaml); a Cloud usa um único arquivo de dependências e procura primeiro na pasta do app | **Alta** (o app não subiria) | Criado `app/requirements.txt`; validado em ambiente virgem (Python 3.13): app abre sem erro. Teste confere que cobre todos os módulos importados (achou um `yaml` que faltava) | Resolvido |
| 2 | Gasto descontrolado: o único limite era 3 por sessão, contornável recarregando a página | **Alta** | Limite global (40/dia, 12/hora, configurável) + chave de emergência `GENERATION_ENABLED` + uma só chamada para a mesma pessoa/dia em sessões simultâneas | Resolvido no app; **limite no console da Anthropic depende de você** |
| 3 | App público: qualquer pessoa com o link consome a cota diária e pode impedir o uso do grupo; o app público pode ser indexado por buscadores | Média | **Aceito pela usuária** (app público sem login). Contenção: limites 40/dia e 12/hora, limite de gastos na Anthropic, chave de emergência; compartilhar o link só com o grupo; se houver abuso, pausar com `GENERATION_ENABLED = "false"` ou passar o app para privado nas configurações | Aceito |
| 4 | Hash do cache (data/hora/local) tem pouca entropia: quem obtivesse os arquivos poderia adivinhá-lo | Baixa (na Cloud ninguém lê o disco) | Sal secreto opcional `CACHE_SALT` (HMAC); gravação atômica do cache | Resolvido; **precisa do Secret na publicação** |
| 5 | Acesso entre usuários | Baixa | Não há contas; `session_state` é por sessão; o cache só devolve mensagem a quem informar exatamente os mesmos dados (equivale a gerar a própria); nada lista o cache. Testes cobrem | Sem risco identificado |
| 6 | Chave da Anthropic | Média | Lida só no servidor (ambiente ou `st.secrets`); nunca vai ao navegador, ao estado da sessão nem aos logs; erros amigáveis sem detalhes (teste); `secrets.toml` e `.cache/` ignorados pelo git; teste varre o repositório atrás de chaves/tokens | Resolvido; a usuária já tem limite de gastos na Anthropic |
| 7 | Dados pessoais versionados: a data/hora de nascimento da usuária aparece nos testes (repositório privado) | Baixa se o repositório continuar privado | Sem alteração: o histórico do git manteria o dado mesmo se os testes fossem trocados | Repositório mantido **privado** (decisão da usuária) |
| 8 | Entradas enormes enviadas ao serviço de localização | Baixa | Limite de 100 caracteres (cidade) e 60 (país), na interface e na validação | Resolvido |
| 9 | Nominatim (gratuito): política de 1 requisição/s e identificação do app; muitos usuários podem causar bloqueio | Média/baixa para grupo pequeno | Busca cacheada por 24 h; sem alteração de serviço | Limitação registrada |
| 10 | Detalhes de erro na tela | Baixa | A Cloud força `showErrorDetails = false`; o app não imprime dados nem a chave | Sem ação |
| 11 | Privacidade/termos | Média | Texto no expander "Privacidade e termos de uso" (fora da mensagem); `docs/privacidade.md` com mapa de dados | Resolvido como rascunho; contato para pedidos de dados e revisão jurídica ficam como pendência para antes de ampliar o grupo |

Também conferido, sem problemas: texto digitado é escapado antes de ir ao HTML; apenas fontes são servidas como arquivos estáticos; o prompt enviado à Anthropic não contém nome, data, hora nem local de nascimento (testes).

## Limites de uso (o que protege o seu bolso)
Camadas, da mais interna para a mais externa:
1. **Cache:** mensagem do dia já guardada = 0 chamadas.
2. **Sessão:** 3 mensagens novas por sessão.
3. **Global:** 40 mensagens novas por dia e 12 por hora, somando todas as sessões do servidor (`src/app/limits.py`). Pior caso diário ≈ 40 x US$ 0,003 ≈ **US$ 0,12** (≈ US$ 3,60 por mês).
4. **Chave de emergência:** `GENERATION_ENABLED = "false"` nos Secrets pausa toda geração nova.
5. **Console da Anthropic (a proteção final, gratuita):** limite mensal de gastos na organização/workspace, com uma chave exclusiva para este app. É a única que vale mesmo se o servidor reiniciar e o contador local zerar.

Configuração (Secrets ou ambiente): `MAX_DAILY_GENERATIONS`, `MAX_HOURLY_GENERATIONS`, `GENERATION_ENABLED`, `CACHE_SALT`.

## Cache e contador na hospedagem (Streamlit Community Cloud)
- O disco do app é **efêmero**: cache e contador valem enquanto o app estiver de pé. Apps sem tráfego por 12 h entram em repouso; a documentação não garante o que acontece com arquivos locais no repouso ou no reinício.
- Efeito: depois de um reinício, a mensagem do dia é gerada de novo (1 chamada por pessoa) e o contador do dia volta a zero. O gasto fica limitado por (reinícios + 1) x 40 mensagens e, em última instância, pelo limite do console da Anthropic.
- Várias pessoas ao mesmo tempo: o app roda em um processo com várias sessões (threads). Escritas atômicas e trava por pessoa/dia evitam arquivo pela metade e chamada duplicada; o contador usa trava de processo e de arquivo.
- Mensagens `daily-3/4/5` antigas continuam intactas em disco; as novas usam `<data>.<versão>.json`.

### Opções se for preciso persistência (nada disso foi implementado)
| Opção | Custo | Esforço | O que resolve |
|---|---|---|---|
| A. Só o limite do console da Anthropic (recomendada agora) | grátis | nenhum código | teto de gasto real, independente de reinícios |
| B. Google Sheets (conexão do Streamlit + conta de serviço) | grátis | médio | contador e cache persistentes; lento, para pouco volume |
| C. Supabase / Upstash Redis / Cloudflare KV (plano gratuito) | grátis | médio | contador atômico e cache persistentes; exige conta e mais um Secret |
Banco de dados só se justifica se a perda do cache incomodar ou o grupo crescer; para um grupo pequeno, A basta.

## Dependências e configuração da Cloud
- Arquivo de dependências: `app/requirements.txt` (streamlit, kerykeion, geopy, timezonefinder, jsonschema, anthropic, pyyaml).
- Arquivo principal: `app/streamlit_app.py`. Python: escolher **3.13** nas configurações avançadas (a versão testada).
- Secrets (TOML): `ANTHROPIC_API_KEY`, `CACHE_SALT` (texto aleatório longo) e, opcionalmente, os limites.
- Repositório privado: a Cloud usa a permissão `repo` do GitHub e uma chave de leitura (deploy key).
- Limites informados pela Cloud (fev/2024, podem mudar): até ~2,7 GB de memória; o app é baixo em consumo.

## Limitações conhecidas
- Contador e cache perdem-se se o servidor reiniciar (ver acima); só o console da Anthropic é permanente.
- Sem login, o app público não distingue pessoas: o limite diário é compartilhado. Use app privado para o grupo.
- Nominatim gratuito e sem contato de identificação além do nome do app.
- A atualização de código no GitHub reinicia o app (e zera cache/contador).
- Testado só no Chrome (desktop e janela de celular); falta Safari e aparelhos reais (Fase 2).
- Texto de privacidade é um rascunho (ver `docs/privacidade.md`).

## Decisões
Tomadas pela usuária em 2026-11-17: app público sem login; repositório privado; limites 40/dia e 12/hora; limite de gastos já configurado na Anthropic; persistência extra não será implementada (opção A: só o limite do console).
Pendentes (não bloqueiam o teste com grupo pequeno): contato nos textos de privacidade, restrição de idade e revisão jurídica antes de ampliar o público.

## Testes
`python -m pytest` → 437 passando (novos: `tests/test_app_limits.py`, `tests/test_deploy_config.py`, casos de limite global, privacidade e entradas em `tests/test_app_ui.py` e `tests/test_app_validation.py`). Verificado também em navegador real (LLM simulado): duas sessões separadas com limite de 1/dia → 1 chamada e o aviso para a segunda pessoa.
