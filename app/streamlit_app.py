"""Mensagem Astral — interface web (Streamlit). Telas e estado; lógica em src/, visual em app/ui/."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from app.ui import components as ui
from src.app import service
from src.app.geo import GeoError, search_places
from src.app.validation import MIN_DATE, check_local_time, validate_form
from src.transits.cache import DailyCache

st.set_page_config(page_title="Mensagem Astral", page_icon="✨", layout="centered")
st.markdown(ui.theme_style_tag(), unsafe_allow_html=True)

SS = st.session_state
SS.setdefault("page", "form")
SS.setdefault("gen_count", 0)
SS.setdefault("saved", {})                                        # valores do formulário, para o botão "Voltar"
PREVIEW = os.environ.get("MENSAGEM_ASTRAL_PREVIEW", "")        # só para revisar o visual: result
SAMPLE = ("Hoje pode ser um bom dia para compartilhar uma ideia ou conversar sobre algo que você vem planejando.\n\n"
          "Vale perceber se a busca por reconhecimento está influenciando suas decisões. Uma conversa sincera "
          "pode trazer uma perspectiva diferente.")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]


@st.cache_resource(show_spinner=False)
def get_kb():
    return service.load_kb()


@st.cache_data(ttl=86400, show_spinner=False)
def find_places(city: str, country: str):
    return search_places(city, country)


def go(page: str):
    SS.page = page
    st.rerun()


def shell(hero_html: str):
    st.markdown(ui.corners() + hero_html, unsafe_allow_html=True)


def about():
    with st.expander("Sobre a astrologia no Mensagem Astral"):
        st.write("A astrologia é uma linguagem simbólica para refletir sobre o dia. Não é uma ciência nem uma "
                 "previsão, e as mensagens são um convite à reflexão, não uma orientação médica, financeira ou jurídica. "
                 "Não pedimos login e não guardamos seus dados de nascimento: só a mensagem do dia, identificada por um código.")


def proceed(place, offset):
    """Valida o instante de nascimento no fuso do local, calcula o mapa e segue para a mensagem."""
    f = SS.form
    if service.birth_in_future(place, f["data"], f["hora"]):
        st.error("Esse horário de nascimento ainda não aconteceu. Confira a data e o horário.")
        return
    try:
        with st.spinner("Calculando o seu mapa..."):
            SS.chart = service.build_chart(place, f["data"], f["hora"], offset)
    except Exception:
        st.error("Não foi possível calcular o mapa com esses dados. Confira o horário e o local.")
        return
    SS.generate_on_arrival = True          # o clique do botão principal é a autorização para gerar a mensagem
    go("result")


# ------------------------------------------------------------------ formulário (tela inicial)
def page_form():
    shell(ui.hero_form())
    st.title("Mensagem Astral")
    st.markdown(ui.divider() + ui.subtitle("Uma mensagem do universo para você, com base no seu mapa astral."),
                unsafe_allow_html=True)
    today = service.today_local()
    sv = SS.saved
    with st.form("nascimento", border=False):
        nome = st.text_input("Nome (opcional)", value=sv.get("nome", ""), max_chars=60,
                             placeholder="Seu nome (opcional)", label_visibility="collapsed")
        data = st.date_input("Data de nascimento", value=sv.get("data"), min_value=MIN_DATE, max_value=today,
                             format="DD/MM/YYYY", label_visibility="collapsed")
        hora = st.time_input("Horário de nascimento", value=sv.get("hora"), step=60, label_visibility="collapsed")
        cidade = st.text_input("Cidade de nascimento", value=sv.get("cidade", ""),
                               placeholder="Cidade de nascimento (ex.: São Paulo, SP)", label_visibility="collapsed")
        with st.expander("Nasceu fora do Brasil?"):
            pais = st.text_input("País", value=sv.get("pais", "Brasil"), label_visibility="collapsed")
        enviado = st.form_submit_button("Receber minha mensagem", type="primary", use_container_width=True)
        st.markdown(ui.moon_row() + ui.scene(), unsafe_allow_html=True)
    st.markdown(ui.privacy_note("Seus dados são usados apenas para calcular seu mapa astral e gerar sua mensagem diária."),
                unsafe_allow_html=True)
    about()
    if not enviado:
        return
    SS.saved = {"nome": nome, "data": data, "hora": hora, "cidade": cidade, "pais": pais}
    erros = validate_form(nome, data, hora, cidade, pais, today)
    if erros:
        for e in erros:
            st.error(e)
        return
    try:
        with st.spinner("Procurando a cidade..."):
            places = find_places(cidade.strip(), pais.strip())
    except GeoError as e:
        st.error(str(e))
        return
    SS.form = {"nome": (nome or "").strip(), "data": data, "hora": hora}
    SS.places = places
    if len(places) == 1 and check_local_time(data, hora, places[0].tz).status == "ok":
        proceed(places[0], None)             # caso comum: segue direto para a mensagem
    else:
        go("confirm")


# ------------------------------------------------------------------ confirmação (local e horário)
def page_confirm():
    shell(ui.hero_form())
    st.title("Confirme o local")
    f, places = SS.form, SS.places
    if len(places) > 1:
        idx = st.radio("Encontramos mais de um lugar. Qual é o seu?", range(len(places)),
                       format_func=lambda i: places[i].label)
    else:
        idx = 0
        st.write(f"**{places[0].label}**")
    place = places[idx]
    check = check_local_time(f["data"], f["hora"], place.tz)
    offset = None
    if check.status == "nonexistent":
        st.error(check.message())
    elif check.status == "ambiguous":
        st.warning(check.message())
        opcoes = {f"Horário de verão (UTC{check.offsets_hours[0]:+g})": check.offsets_hours[0],
                  f"Horário padrão (UTC{check.offsets_hours[1]:+g})": check.offsets_hours[1]}
        offset = opcoes[st.radio("Qual vale?", list(opcoes))]
    col1, col2 = st.columns(2)
    if col1.button("Voltar", key="back_confirm", use_container_width=True):
        go("form")
    if col2.button("Ver minha mensagem de hoje", type="primary", disabled=check.status == "nonexistent",
                   use_container_width=True):
        proceed(place, offset)
    st.markdown(ui.scene(), unsafe_allow_html=True)


# ------------------------------------------------------------------ mensagem do dia
def result_header(day, nome):
    shell(ui.hero_result())
    st.markdown(ui.date_line(f"{day.day} de {MESES[day.month - 1]} de {day.year}".upper()), unsafe_allow_html=True)
    st.title("Sua mensagem de hoje")
    if nome:
        st.markdown(ui.greeting(nome), unsafe_allow_html=True)


def result_footer(chart):
    st.markdown(ui.scene(), unsafe_allow_html=True)
    r = chart["resumo"]
    with st.expander("Seu mapa"):
        st.write(f"**Sol:** {r['signo_solar']} · **Lua:** {r['signo_lunar']} · **Ascendente:** {r['ascendente']}")
    if st.button("Começar de novo", use_container_width=True):
        for k in ("form", "places", "chart", "saved", "generate_on_arrival"):
            SS.pop(k, None)
        go("form")
    st.markdown(ui.footer_note("Mensagem Astral · versão de demonstração"), unsafe_allow_html=True)


def page_result():
    chart, f = SS.chart, SS.form
    day = service.today_local()
    kb, cache = get_kb(), DailyCache(service.cache_dir())
    auto = SS.pop("generate_on_arrival", False)        # só vale logo após o clique no botão principal
    result_header(day, f["nome"])
    slot = st.container()                              # a moldura aparece aqui, depois da geração
    msg = service.cached_message(kb, chart, day, cache)
    note = ""
    if msg is None:
        key = service.get_api_key(st.secrets)
        if not key:
            note = "A geração de mensagens está desativada neste ambiente (chave de acesso não configurada)."
        elif SS.gen_count >= service.MAX_GENERATIONS_PER_SESSION:
            note = "Você atingiu o limite de mensagens desta sessão. Volte mais tarde."
        else:
            falhou = SS.get("gen_failed", False)
            clicou = False
            botao_slot = st.empty()                    # o botão some assim que a mensagem é gerada
            if not auto:
                note = "Não foi possível gerar a mensagem agora." if falhou else "Sua mensagem de hoje ainda não foi gerada."
                with botao_slot:
                    clicou = st.button("Tentar novamente" if falhou else "Gerar mensagem de hoje", type="primary",
                                       use_container_width=True, key="gen")
            if auto or clicou:
                try:
                    with slot, st.spinner("Escrevendo a sua mensagem..."):
                        msg = service.generate_message(kb, chart, day, service.build_llm(key), cache)
                    SS.gen_count += 1
                    SS.gen_failed = False
                    botao_slot.empty()
                except Exception as e:
                    SS.gen_failed = True
                    st.error(service.friendly_error(e))
                    note = "Não foi possível gerar a mensagem agora."
                    if auto:        # o botão ainda não foi desenhado nesta execução: desenha para a próxima tentativa
                        with botao_slot:
                            st.button("Tentar novamente", type="primary", use_container_width=True, key="gen")
    with slot:
        st.markdown(ui.message_frame(msg.text if msg else None, note), unsafe_allow_html=True)
    result_footer(chart)


def page_preview_result():
    """Só para revisar o visual (MENSAGEM_ASTRAL_PREVIEW=result): mensagem de exemplo, sem API e sem cálculo."""
    result_header(service.today_local(), "")
    st.markdown(ui.message_frame(SAMPLE), unsafe_allow_html=True)
    st.markdown(ui.scene(), unsafe_allow_html=True)
    st.markdown(ui.footer_note("Pré-visualização do visual · mensagem de exemplo"), unsafe_allow_html=True)


PAGES = {"form": page_form, "confirm": page_confirm, "result": page_result}
if PREVIEW == "result":
    page_preview_result()
else:
    if SS.page in ("confirm", "result") and ("form" not in SS or ("chart" not in SS and SS.page == "result")):
        SS.page = "form"
    PAGES[SS.page]()
