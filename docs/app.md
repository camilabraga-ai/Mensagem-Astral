# Interface web (Etapa 6)

MVP em Streamlit que reaproveita toda a arquitetura Python existente. Sem login, sem banco de dados, sem serviços pagos além da API da Anthropic (Claude Haiku 5.5).

## Executar localmente
```bash
cd Mensagem-Astral
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-app.txt
export ANTHROPIC_API_KEY="sk-ant-..."        # opcional: sem a chave, a geração fica desativada
streamlit run app/streamlit_app.py
```
Abre em http://localhost:8501. Alternativa à variável de ambiente: crie `.streamlit/secrets.toml` (já ignorado pelo git):
```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

## Fluxo
1. **Tela inicial = formulário** (como no mockup): nome (opcional), data, horário e cidade; o país (padrão Brasil) fica em "Nasceu fora do Brasil?". Validação em português. O aviso sobre a natureza simbólica da astrologia fica em "Sobre a astrologia no Mensagem Astral" (e nos Termos de Uso), nunca no corpo da mensagem.
2. **Local:** a cidade é buscada (Nominatim/OpenStreetMap). No caso comum (um resultado e horário sem ambiguidade) segue direto para a mensagem; se houver mais de um resultado ou dúvida de horário, aparece a tela "Confirme o local".
4. **Horário de verão:** o motor natal lança erro para horários que não existiram ou que se repetiram na mudança de horário de verão. A interface detecta esses casos: horário inexistente bloqueia com uma explicação; horário ambíguo pede a escolha entre "horário de verão" e "horário padrão" (resolvida com um fuso fixo, sem alterar o motor).
5. **Mensagem de hoje:** pipeline da Etapa 5 (trânsitos, RAG, Haiku, fidelidade).

## Identidade visual (mockup aprovado)
Estrutura separada entre decoração e função:
```
app/streamlit_app.py       telas e estado (campos e botões são componentes nativos do Streamlit)
app/ui/theme.css           tema: preto + dourado, tipografia, campos, botões, moldura (CSS personalizado)
app/ui/ornaments.py        ilustrações em SVG puro (sol, arco zodiacal, roda com a Lua, nuvens, montanhas, ícones)
app/ui/components.py       monta o HTML dos ornamentos e da moldura (escapa todo texto dinâmico)
app/static/fonts/          Cinzel (títulos) e Cormorant Garamond (texto), licença OFL, hospedadas localmente
```
- Os desenhos usam `currentColor`: a cor dourada vem do CSS (`--ma-gold`), então mudar a paleta é editar uma variável.
- Ícones dos campos são SVGs embutidos no CSS. Nenhum recurso externo (nem fontes do Google) é carregado.
- Layout mobile-first: cartão de até 520 px centralizado no desktop, ocupando a tela no celular.
- **Prévia do visual sem API e sem cálculo:** `MENSAGEM_ASTRAL_PREVIEW=result streamlit run app/streamlit_app.py` mostra a tela da mensagem com um texto de exemplo (a mensagem do mockup), só para revisar o desenho.
- Os campos de data e hora usam os componentes nativos; o rótulo ("Data de nascimento", "Horário de nascimento") aparece como placeholder via CSS e os segmentos `dd/mm/aaaa` e `HH:mm` surgem ao tocar no campo.

## Controle de custos
- A mensagem em cache (mesma pessoa, mesmo dia, mesmo modelo e versão do prompt) aparece **sem nenhuma chamada**.
- A chamada à API só acontece quando a pessoa clica em **Gerar mensagem de hoje**; nada é gerado ao abrir a página.
- Limite de 3 gerações por sessão (`MAX_GENERATIONS_PER_SESSION`).
- Sem chave configurada, o botão não aparece e a tela explica que a geração está desativada.
- O modelo é `claude-haiku-5-5` (`DEFAULT_MODEL`). Estimativa: ~US$ 0,0013 por mensagem.

## Segurança e privacidade
- A chave vem de `ANTHROPIC_API_KEY` (ambiente) ou dos Secrets do Streamlit; nunca é exibida nem registrada, e as mensagens de erro não a contêm.
- O nome digitado é usado só na saudação; **não é enviado ao modelo**. Data, hora e cidade também não vão no prompt (só signos, graus e textos da base).
- O cache guarda a mensagem, a data, o modelo e os trânsitos, em arquivos identificados por um hash do instante e do local de nascimento; os dados de nascimento não ficam gravados em claro. Pasta padrão: `.cache/mensagens/` (ignorada pelo git; mude com `MENSAGEM_ASTRAL_CACHE_DIR`).

## Testes
`python -m pytest tests/test_app_validation.py tests/test_app_service.py tests/test_app_ui.py`

A interface é testada de ponta a ponta com `streamlit.testing.v1.AppTest`, com a busca de cidades e o LLM simulados (nenhuma rede, nenhuma chamada paga).

## Limitações conhecidas
- A reprodução do mockup é fiel na estrutura e no estilo, mas as ilustrações são desenhos vetoriais próprios (mais simples que as do mockup); dá para trocá-las por SVGs/PNGs finais de um ilustrador sem mexer na lógica.
- Nos navegadores sem suporte a `:has()` (versões antigas), o placeholder dos campos de data e hora mostra os segmentos nativos (`dd/mm/aaaa`, `HH:mm`) em vez do rótulo.
- O serviço gratuito de localização (Nominatim) tem limite de uso e pode falhar ou demorar; a busca é cacheada por 24 h.
- Horário ambíguo usa um fuso fixo escolhido pela pessoa; o horário de referência dos trânsitos (meio-dia) usa esse mesmo fuso fixo.
- Sem login: não há histórico por usuária nem proteção contra uso abusivo além do limite por sessão (que se zera ao recarregar a página).
- O cache é local ao servidor; em hospedagens com disco efêmero ele se perde ao reiniciar.
- A página mostra só a mensagem do dia (não há mensagens de outros dias nem perguntas e respostas).
- A aparência foi conferida em capturas do Chrome (celular e desktop); falta a revisão da usuária em outros navegadores e aparelhos.

## Próximos passos para publicação (não executados)
1. Revisar a interface num navegador (desktop e celular) e ajustar a identidade visual.
2. Escolher a hospedagem (por exemplo Streamlit Community Cloud) e cadastrar `ANTHROPIC_API_KEY` nos Secrets dela, com **limite de gasto** configurado no console da Anthropic.
3. Trocar a busca de cidades por um serviço com garantia de uso em produção (ou manter o Nominatim com cache e respeitando a política de uso).
4. Cache persistente (ou aceitar o custo de regerar após reinícios) e limite de uso por IP/dispositivo.
5. Redigir os Termos de Uso e a política de privacidade (LGPD): o aviso sobre a natureza simbólica da astrologia e o tratamento de dados de nascimento.
6. Decidir o repositório (hoje privado) e o domínio.
