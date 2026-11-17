"""Mensagem Astral — interface web (Streamlit). Toda a lógica fica em src/; aqui só telas e estado."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from src.app import service
from src.app.geo import GeoError, search_places
from src.app.validation import MIN_DATE, check_local_time, validate_form
from src.transits.cache import DailyCache

st.set_page_config(page_title="Mensagem Astral", page_icon="✨", layout="centered")

st.markdown("""
<style>
.stApp { background: radial-gradient(1200px 600px at 50% -10%, #2a2150 0%, #120f24 60%); }
h1 { font-weight: 600; letter-spacing: .5px; }
.ma-sub { color: #bdb3d6; font-size: 1.05rem; margin-top: -0.6rem; }
.ma-foot { color: #8f86a8; font-size: .8rem; margin-top: 2rem; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
@media (max-width: 640px) { h1 { font-size: 1.8rem; } }
</style>
""", unsafe_allow_html=True)

SS = st.session_state
SS.setdefault("page", "home")
SS.setdefault("gen_count", 0)


@st.cache_resource(show_spinner=False)
def get_kb():
    return service.load_kb()


@st.cache_data(ttl=86400, show_spinner=False)
def find_places(city: str, country: str):
    return search_places(city, country)


def go(page: str):
    SS.page = page
    st.rerun()


def footer():
    st.markdown('<div class="ma-foot">Mensagem Astral · versão de demonstração · Termos de Uso em breve</div>',
                unsafe_allow_html=True)


# ------------------------------------------------------------------ tela inicial
def page_home():
    st.title("✨ Mensagem Astral")
    st.markdown('<p class="ma-sub">Uma mensagem curta para o seu dia, escrita a partir do seu mapa astral '
                'e do céu de hoje.</p>', unsafe_allow_html=True)
    st.markdown(
        "- Você informa **data, horário e cidade** de nascimento.\n"
        "- Calculamos o seu mapa e os trânsitos do dia.\n"
        "- Você recebe uma mensagem de **70 a 100 palavras**, com uma observação e uma sugestão prática.")
    st.info("A astrologia é uma linguagem simbólica para refletir sobre o dia. Não é uma ciência nem uma "
            "previsão. Não pedimos login e não guardamos seus dados de nascimento: só a mensagem do dia, "
            "identificada por um código.")
    if st.button("Começar", type="primary", use_container_width=True):
        go("form")
    footer()


# ------------------------------------------------------------------ formulário
def page_form():
    st.title("Seus dados de nascimento")
    today = service.today_local()
    with st.form("nascimento"):
        nome = st.text_input("Nome (opcional)", max_chars=60)
        data = st.date_input("Data de nascimento", value=None, min_value=MIN_DATE, max_value=today,
                             format="DD/MM/YYYY")
        hora = st.time_input("Horário de nascimento", value=None, step=60)
        cidade = st.text_input("Cidade de nascimento", placeholder="Ex.: São Paulo, SP")
        pais = st.text_input("País", value="Brasil")
        enviado = st.form_submit_button("Continuar", type="primary", use_container_width=True)
    if st.button("Voltar"):
        go("home")
    if not enviado:
        return
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
    go("confirm")


# ------------------------------------------------------------------ confirmação (local e horário)
def page_confirm():
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
    if col1.button("Voltar", key="back_confirm"):
        go("form")
    if col2.button("Ver minha mensagem de hoje", type="primary", disabled=check.status == "nonexistent"):
        try:
            with st.spinner("Calculando o seu mapa..."):
                SS.chart = service.build_chart(place, f["data"], f["hora"], offset)
        except Exception:
            st.error("Não foi possível calcular o mapa com esses dados. Confira o horário e o local.")
            return
        go("result")


# ------------------------------------------------------------------ mensagem do dia
def show_message(msg):
    with st.container(border=True):
        for par in msg.text.split("\n\n"):
            st.markdown(par)


def page_result():
    chart, f = SS.chart, SS.form
    day = service.today_local()
    st.title(f"Olá, {f['nome']}" if f["nome"] else "Sua mensagem de hoje")
    st.caption(day.strftime("%d/%m/%Y"))
    kb, cache = get_kb(), DailyCache(service.cache_dir())
    msg = service.cached_message(kb, chart, day, cache)
    if msg is None:
        key = service.get_api_key(st.secrets)
        if not key:
            st.info("A geração de mensagens está desativada neste ambiente (chave de acesso não configurada).")
        elif SS.gen_count >= service.MAX_GENERATIONS_PER_SESSION:
            st.warning("Você atingiu o limite de mensagens desta sessão. Volte mais tarde.")
        else:
            st.write("Sua mensagem de hoje ainda não foi gerada.")
            if st.button("Gerar mensagem de hoje", type="primary", use_container_width=True):
                try:
                    with st.spinner("Escrevendo a sua mensagem..."):
                        msg = service.generate_message(kb, chart, day, service.build_llm(key), cache)
                    SS.gen_count += 1
                except Exception as e:
                    st.error(service.friendly_error(e))
    if msg is not None:
        show_message(msg)
    r = chart["resumo"]
    with st.expander("Seu mapa"):
        st.write(f"**Sol:** {r['signo_solar']} · **Lua:** {r['signo_lunar']} · **Ascendente:** {r['ascendente']}")
    if st.button("Começar de novo"):
        for k in ("form", "places", "chart"):
            SS.pop(k, None)
        go("home")
    footer()


PAGES = {"home": page_home, "form": page_form, "confirm": page_confirm, "result": page_result}
if SS.page in ("confirm", "result") and ("form" not in SS or ("chart" not in SS and SS.page == "result")):
    SS.page = "home"
PAGES[SS.page]()
