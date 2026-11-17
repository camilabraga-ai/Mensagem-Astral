# Decisões técnicas

Cada decisão indica **o que a sustenta** (código, testes, documentos ou histórico do git) e sinaliza quando a motivação
original **não está registrada**. Onde há inferência, ela está marcada como tal.

## 1. LLM existente em vez de modelo próprio
- **Fato:** o produto usa a API do Claude; nenhum modelo foi treinado ou ajustado. O pacote `src/models/` está vazio.
- **Sustentação:** o próprio desenho separa responsabilidades: o conhecimento fica na base (224 textos) e o cálculo no
  Kerykeion; o LLM só redige. Isso cabe em uma chamada de API sem treinamento.
- **Não registrado:** não há um documento que compare treinar × usar API. O README inicial já tratava o fine-tuning como "etapa
  posterior" e ele segue adiado. Qualquer justificativa além disso (custo, tempo, dados) seria inferência.

## 2. Por que RAG
- **Sustentação:** o cálculo astrológico é exato, mas a redação precisa de significados. A base própria (`kb/documentos.jsonl`)
  entrega os significados no prompt, em vez de depender do que o modelo "sabe" de astrologia.
- **Efeitos verificáveis no código:** (a) o prompt de sistema manda usar **somente** o que foi enviado; (b)
  `check_faithfulness` compara a mensagem com o que foi calculado e recuperado; (c) a base é auditável (hash, IDs, validação).
- **Origem do conteúdo:** textos escritos com apoio de IA generativa a partir de instruções do projeto e revisados por uma
  pessoa (os 12 de signos, em 16/11/2026); sem trechos de obras de terceiros (`kb/ORIGEM.md`). Os demais textos **não**
  têm registro de revisão individual.

## 3. Por que recuperação estruturada (e não embeddings + banco vetorial)
- **Sustentação no código:** o mapa calculado já fornece as entidades exatas (planeta, signo, casa, aspecto);
  `KnowledgeBase.lookup` faz correspondência exata de entidades, e o ID do documento é derivado delas. Testes mostram que as
  144 combinações signo × casa e toda a grade planeta × signo têm documento (cobertura completa, resultado determinístico).
  A mesma informação permite à checagem de fidelidade saber exatamente o que entrou no prompt.
- **Infraestrutura:** nada a indexar, hospedar ou reindexar; funciona no disco efêmero da hospedagem.
- **Preparado, mas não usado:** `KnowledgeBase.rag_records()` já devolve texto indexável e metadados. O `requirements.txt`
  inicial listava `sentence-transformers` com FAISS ou Chroma "a decidir"; a mudança para metadados ocorreu no commit da
  Etapa 4 (`ed29890`) **sem uma justificativa escrita naquele momento**. As razões acima são as que o código sustenta hoje.
- **Trade-off assumido:** perde-se busca semântica. Não dá para responder perguntas livres sem entidades do mapa, e
  não houve experimento comparando com embeddings (ver pendências em `avaliacao.md`).

## 4. Por que Claude Haiku 5.5
- **Registrado:** o commit `e7ffd96` diz "Claude Haiku 5.5 como modelo padrão (menor custo)". É o `DEFAULT_MODEL`.
- **Medido:** ≈ US$ 0,001 por mensagem com o preço assumido (`docs/avaliacao.md`), compatível com um app gratuito.
- **Qualidade:** o Haiku produziu mensagens aprovadas por leitura manual da autora; **não houve comparação** com modelos
  maiores. `AnthropicLLM(model=...)` permite trocar sem alterar o resto.
- **Configuração:** `effort: "low"` e `max_tokens=4000` (a saída chegou a 1.970 tokens com limite de 2.000 no primeiro
  teste, por causa do raciocínio interno; o limite subiu para ter folga). Não houve teste de outros níveis de esforço.

## 5. Engenharia de prompts
Histórico (commits e `PROMPT_VERSION`):
- Mensagem natal: 250–350 palavras; depois um reforço para não copiar frases dos textos de referência (tokens de saída caíram
  de ~1.800–1.970 para 830–1.590 por mensagem, ver `docs/rag.md`).
- `daily-2`/`daily-3`: 70–100 palavras, até 2 parágrafos, tom conversacional, sem poesia e sem aviso científico no texto.
- `daily-4` → `daily-5`: a astrologia passou a ser só raciocínio interno; abertura com situação concreta.
- `daily-6`: após a autora perceber mensagens parecidas em mapas diferentes, foram **removidos os exemplos concretos do prompt**
  (o modelo os copiava) e o tema passou a decorrer do trânsito de maior peso (planetas lentos = tema de fundo; Lua e Marte = humor e ação).

Técnicas em uso: regras numeradas e explícitas; lista de expressões proibidas; limite duro de palavras com meta (~85);
separação entre "raciocínio interno" (dados) e o que o leitor vê; mensagens recentes no prompt para evitar repetição;
alertas pós-geração (`check_faithfulness`, `check_no_jargon`). Os alertas **não bloqueiam**: foi uma escolha de simplicidade;
o efeito é que um texto com jargão ainda seria entregue (nos 9 testes guardados, ambos ficaram em 0).
Cada mudança de prompt exige novo `PROMPT_VERSION`, que invalida o cache sem apagar as mensagens anteriores.

## 6. Cache, limites de geração e controle de custos
Camadas, da mais interna para a mais externa:
1. **Cache** por pessoa, dia, modelo e versão do prompt (`<pessoa>/<data>.<versão>.json`, escrita atômica). Hit custa zero.
   Duas sessões pedindo a mesma pessoa e dia ao mesmo tempo pagam uma só chamada (trava por chave).
2. **Limite por sessão:** 3 mensagens novas (contornável recarregando a página, por isso não é suficiente).
3. **Limite global no servidor:** 40 por dia (fuso de São Paulo) e 12 por hora, em contador de arquivo + memória com trava de
   thread e `flock`; toda reserva conta mesmo se a chamada falhar (postura conservadora para custo).
4. **Chave de emergência** `GENERATION_ENABLED=false`.
5. **Limite de gastos no console da Anthropic**, configurado pela autora; é o único que sobrevive a um reinício.

Privacidade do cache: o código da pessoa é um hash do instante UTC e das coordenadas (2 casas decimais, para o serviço de
cidades não gerar chamadas novas por variações mínimas); com `CACHE_SALT` vira HMAC, pois data/hora/local têm pouca
entropia e um hash simples poderia ser adivinhado por força bruta.

Por que arquivos e não banco: o escopo era um MVP de baixo volume sem infraestrutura extra. As alternativas avaliadas
(Google Sheets, Supabase/Redis/KV) estão em `docs/etapa7_progresso.md` e **não foram implementadas**.

## 7. Trade-offs do Streamlit Community Cloud
| Aspecto | Consequência | Como foi tratado |
|---|---|---|
| Gratuito, deploy a partir do GitHub | publicação simples | `app/requirements.txt` na pasta do app (a Cloud usa um único arquivo de dependências) |
| Disco efêmero | cache e contador se perdem em reinício, repouso (12 h sem tráfego) e a cada `git push` | aceito; limite do console da Anthropic como teto; documentado |
| App público sem login | qualquer pessoa com o link consome a cota diária | decisão da autora; limites globais, chave de emergência, divulgar o link só ao grupo |
| Repositório privado | exige permissão de leitura da Cloud | configurado; app público a partir de repositório privado precisa ser marcado como público em Sharing |
| Secrets na plataforma | chave fora do repositório | `st.secrets` + teste de varredura |
| Streamlit reexecuta o script a cada interação | risco de chamadas repetidas | a API só é chamada após o clique no botão principal; estado em `session_state` |
| Selo "Hosted with Streamlit" | sobrepõe o rodapé no celular | limitação registrada |
Não há observabilidade além dos logs da plataforma e nem monitoramento de gastos próprio.

## 8. Limitações e quando considerar fine-tuning
O fine-tuning (LoRA) foi **adiado e não implementado**. O que a base já permite: `qa.schema.json` e o campo `split_grupo`
(divisão sem vazamento) foram desenhados para pares pergunta-resposta, mas **não existe nenhum dataset de treino** no
repositório.

Condições razoáveis para considerar (recomendação, não decisão registrada):
- existir uma avaliação automática e um conjunto fixo mostrando um **ganho mensurável** que prompt, RAG e troca de modelo não alcançam
  (por exemplo, consistência de estilo ou redução de custo com um modelo menor);
- ter dados de treino com direitos claros e revisão de qualidade (hoje a base tem 224 textos de ~123 palavras, pouco para isso);
- o custo por mensagem ou a latência virarem um problema real em volume maior.
Sem essas condições, o ganho esperado é baixo diante do custo atual (~US$ 0,001 por mensagem).

Limitações do sistema que as decisões acima não resolvem: só Sol, Lua e Ascendente natais nos trânsitos; sem textos de trânsito
nem de casas em trânsito na base; qualidade avaliada manualmente; fidelidade checada por palavras.
