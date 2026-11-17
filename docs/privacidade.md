# Privacidade e termos de uso (rascunho para revisão)

O texto exibido no aplicativo está em `app/ui/legal.py` (expander "Privacidade e termos de uso", tela inicial). Fica **fora** do corpo da mensagem diária.

## Mapa de dados (o que acontece com cada informação)
| Dado | Onde passa | Fica guardado? |
|---|---|---|
| Nome (opcional) | só na sessão do navegador, para a saudação | Não. Não vai ao modelo nem ao cache |
| Data, hora e cidade de nascimento | sessão; a cidade vai ao Nominatim/OpenStreetMap para achar coordenadas | Não em claro. O cache usa um código (HMAC/hash) calculado desses dados |
| Posições astrológicas, data de hoje, mensagens anteriores da própria pessoa | Anthropic (API do Claude, EUA) | Conforme a política da Anthropic |
| Mensagem do dia | cache em disco do servidor, chave = código da pessoa + data + versão do prompt | Sim, temporário (some se o disco for apagado) |
| Contador de gerações (instantes, sem identificação) | disco do servidor | Sim, temporário |

## Pendências antes de ampliar o grupo (não são aconselhamento jurídico)
1. **Contato** para pedidos sobre dados (LGPD): o texto ainda não traz um e-mail. Como o grupo é pequeno e convidado, pode-se usar "o contato de quem convidou você"; ou definir um e-mail do projeto.
2. **Base legal e controlador:** para um grupo pequeno de convidados, o consentimento no uso é o mais simples; se o público crescer, vale revisão jurídica do texto.
3. **Menores de 18 anos:** o texto pede acompanhamento; decidir se haverá restrição de idade.
4. **Política de retenção da Anthropic:** confirmar no contrato/console como a API trata dados (retenção, uso para treino) e ajustar o texto se necessário.
