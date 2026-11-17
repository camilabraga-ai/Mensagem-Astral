"""Configuração de implantação (Streamlit Community Cloud): dependências, segredos fora do repositório, arquivos servidos."""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# nome do módulo importado -> pacote no requirements
PACOTE = {"yaml": "pyyaml", "streamlit": "streamlit", "anthropic": "anthropic", "kerykeion": "kerykeion",
          "geopy": "geopy", "timezonefinder": "timezonefinder", "jsonschema": "jsonschema"}
LOCAIS = {"src", "app", "tests"}
OPCIONAIS = {"torch"}     # src/common/env.py: import dentro de try (relatório de GPU do Colab); o app não o usa


def pacotes(arquivo: Path) -> set[str]:
    nomes = set()
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#")[0].strip()
        if linha and not linha.startswith("-"):
            nomes.add(re.split(r"[<>=!~\[; ]", linha, maxsplit=1)[0].lower().replace("_", "-"))
    return nomes


def modulos_de_terceiros(pasta: Path) -> set[str]:
    achados = set()
    for f in pasta.rglob("*.py"):
        for no in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(no, ast.Import):
                achados |= {a.name.split(".")[0] for a in no.names}
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                achados.add(no.module.split(".")[0])
    return {m for m in achados if m not in sys.stdlib_module_names and m not in LOCAIS and m not in OPCIONAIS and m != "__future__"}


def test_requirements_do_app_cobrem_todos_os_modulos_importados_pelo_app_e_pelo_src():
    """A Cloud usa UM arquivo de dependências, achado primeiro na pasta do app: se faltar algo, o app quebra no ar."""
    declarados = pacotes(ROOT / "app" / "requirements.txt")
    usados = modulos_de_terceiros(ROOT / "app") | modulos_de_terceiros(ROOT / "src")
    faltam = {m for m in usados if PACOTE.get(m, m).lower() not in declarados}
    assert not faltam, f"faltam em app/requirements.txt: {faltam}"


def test_requirements_do_app_incluem_tudo_que_os_arquivos_por_etapa_pedem():
    esperado = set()
    for nome in ("requirements-app.txt", "requirements-astrology.txt", "requirements-kb.txt", "requirements-rag.txt"):
        esperado |= pacotes(ROOT / nome)
    assert esperado <= pacotes(ROOT / "app" / "requirements.txt")


def test_requirements_do_app_nao_trazem_o_que_so_o_desenvolvimento_usa():
    assert not ({"pytest", "pandas", "numpy"} & pacotes(ROOT / "app" / "requirements.txt"))


def test_segredos_e_cache_ficam_fora_do_git():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for item in (".streamlit/secrets.toml", ".cache/", "secrets*", ".env"):
        assert item in gi


def test_nenhuma_chave_ou_token_no_repositorio():
    padrao = re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,}")
    ignorar = {".git", ".cache", "__pycache__", ".pytest_cache", ".venv", "v"}
    suspeitos = []
    for f in ROOT.rglob("*"):
        if f.is_file() and not (set(f.relative_to(ROOT).parts) & ignorar) and f.suffix in {
                ".py", ".md", ".toml", ".txt", ".json", ".ipynb", ".yaml", ".yml", ".css", ".cfg"} \
                and f.name != "secrets.toml":
            if padrao.search(f.read_text(encoding="utf-8", errors="ignore")):
                suspeitos.append(str(f.relative_to(ROOT)))
    assert not suspeitos, suspeitos


def test_so_fontes_sao_servidas_como_arquivos_estaticos():
    permitidos = {".ttf", ".md"}
    extras = [str(f) for f in (ROOT / "app" / "static").rglob("*") if f.is_file() and f.suffix not in permitidos]
    assert not extras


def test_configuracao_do_streamlit_nao_coleta_uso_e_nao_expoe_detalhes_de_erro():
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "gatherUsageStats = false" in cfg
    assert "showErrorDetails" not in cfg or 'showErrorDetails = "none"' in cfg or "showErrorDetails = false" in cfg
