"""Leitura das paginas do Promax: formularios, frames, alertas e links de relatorio."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

URL_RELATORIO_RE = re.compile(
    r"""(?P<url>(?:https?://[^"'<> ]+/|(?:\.\./)+|/pw/|/)?tmp/rels/[^"'<> ]+\.(?:csv|pdf|txt)(?:\.inf)?)""",
    re.IGNORECASE,
)
ALERTA_RE = re.compile(r"""\balert\s*\(\s*(['"])(?P<texto>.*?)\1\s*\)""", re.IGNORECASE | re.DOTALL)
FRAME_SRC_RE = re.compile(r"""<FRAME[^>]*\bSRC\s*=\s*["']([^"']+)["'][^>]*\bname\s*=\s*["']?(\w+)""", re.IGNORECASE)
BOTTOM_ROTINA_RE = re.compile(
    r"""bottom_rotina\.document\.location\.href\s*=\s*["']([^"']+)["']""", re.IGNORECASE
)
UNIDADE_ATIVA_RE = re.compile(r"""document\.all\.unidade\.value\s*=\s*["'](\d+)["']""", re.IGNORECASE)


@dataclass
class Opcao:
    valor: str
    texto: str
    selecionada: bool = False


@dataclass
class Formulario:
    nome: str
    action: str
    metodo: str
    campos: dict[str, str] = field(default_factory=dict)
    opcoes: dict[str, list[Opcao]] = field(default_factory=dict)
    botoes: dict[str, dict[str, str]] = field(default_factory=dict)
    checkboxes: dict[str, str] = field(default_factory=dict)


class _LeitorFormularios(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.formularios: list[Formulario] = []
        self._atual: Formulario | None = None
        self._select: str | None = None
        self._opcao: Opcao | None = None

    def _form(self) -> Formulario:
        # Alguns campos do Promax ficam fora de <form>; agrupamos num formulario implicito.
        if self._atual is None:
            self._atual = Formulario(nome="", action="", metodo="GET")
            self.formularios.append(self._atual)
        return self._atual

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        tag = tag.lower()
        if tag == "form":
            self._atual = Formulario(
                nome=a.get("name", ""), action=a.get("action", ""), metodo=a.get("method", "GET").upper()
            )
            self.formularios.append(self._atual)
        elif tag == "input":
            nome = a.get("name")
            tipo = a.get("type", "text").lower()
            if not nome or tipo in {"submit", "button", "image", "reset", "file"}:
                if nome and tipo in {"submit", "button"}:
                    self._form().botoes[nome] = a
                return
            if tipo == "checkbox":
                self._form().checkboxes[nome] = a.get("value", "on")
            if tipo in {"checkbox", "radio"}:
                if "checked" in a:
                    self._form().campos[nome] = a.get("value", "on")
                else:
                    self._form().campos.setdefault(nome, None)  # type: ignore[arg-type]
                return
            self._form().campos[nome] = a.get("value", "")
        elif tag == "select":
            self._select = a.get("name")
            if self._select:
                self._form().opcoes.setdefault(self._select, [])
        elif tag == "option" and self._select:
            self._opcao = Opcao(valor=a.get("value", ""), texto="", selecionada="selected" in a)
            self._form().opcoes[self._select].append(self._opcao)
        elif tag == "textarea" and a.get("name"):
            self._form().campos[a["name"]] = ""
        elif tag == "button" and a.get("name"):
            self._form().botoes[a["name"]] = a

    def handle_data(self, data):
        if self._opcao is not None:
            self._opcao.texto += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "option":
            self._opcao = None
        elif tag == "select":
            self._select = None
        elif tag == "form":
            self._atual = None


def ler_formularios(html: str) -> list[Formulario]:
    leitor = _LeitorFormularios()
    leitor.feed(html)
    for form in leitor.formularios:
        for nome, opcoes in form.opcoes.items():
            if not opcoes or form.campos.get(nome) is not None:
                continue
            escolhida = next((o for o in opcoes if o.selecionada), opcoes[0])
            form.campos[nome] = escolhida.valor
        for opcoes in form.opcoes.values():
            for o in opcoes:
                o.texto = " ".join(o.texto.split())
        # Checkbox/radio sem marcacao nao vai no POST, igual ao navegador.
        form.campos = {k: v for k, v in form.campos.items() if v is not None}
    return leitor.formularios


def formulario(html: str, nome: str) -> Formulario:
    for form in ler_formularios(html):
        if form.nome.lower() == nome.lower():
            return form
    raise ValueError(f"Formulario '{nome}' nao encontrado na pagina")


def alertas(html: str) -> list[str]:
    return [" ".join(m.group("texto").split()) for m in ALERTA_RE.finditer(html or "")]


def frames(html: str, url_base: str) -> dict[str, str]:
    return {nome.lower(): urljoin(url_base, src.replace("&amp;", "&")) for src, nome in FRAME_SRC_RE.findall(html)}


def url_frame_inferior(html: str, url_base: str) -> str | None:
    achado = BOTTOM_ROTINA_RE.search(html or "")
    return urljoin(url_base, achado.group(1)) if achado else None


def urls_relatorio(html: str, url_base: str) -> list[str]:
    urls: list[str] = []
    for m in URL_RELATORIO_RE.finditer(html or ""):
        url = urljoin(url_base, m.group("url").replace("&amp;", "&"))
        if url not in urls:
            urls.append(url)
    return urls


def unidade_ativa(html_topo: str) -> str | None:
    achado = UNIDADE_ATIVA_RE.search(html_topo or "")
    return achado.group(1) if achado else None


_FUNCAO_JS_RE = re.compile(r"function\s+\w+\s*\([^)]*\)\s*\{")
_ATRIBUI_VALOR_RE = re.compile(
    r"""document\.all\.(\w+)\.value\s*=\s*((?:\s*(?:"[^"]*"|'[^']*')\s*\+?)+)\s*;""", re.IGNORECASE
)
_ATRIBUI_CHECKED_RE = re.compile(r"document\.all\.(\w+)\.checked\s*=\s*(true|false)\s*;", re.IGNORECASE)


def _sem_funcoes(js: str) -> str:
    """Remove corpos de function(){...}: so interessa o que roda quando a tela carrega."""
    partes, inicio = [], 0
    for achado in _FUNCAO_JS_RE.finditer(js):
        if achado.start() < inicio:
            continue
        partes.append(js[inicio:achado.start()])
        profundidade, i = 1, achado.end()
        while i < len(js) and profundidade:
            profundidade += {"{": 1, "}": -1}.get(js[i], 0)
            i += 1
        inicio = i
    partes.append(js[inicio:])
    return "".join(partes)


def valores_de_carga(html: str) -> tuple[dict[str, str], dict[str, bool]]:
    """Valores que os <script> soltos da pagina gravam nos campos ao carregar.

    Ex.: a 02.05.02 preenche periodo, faixas e marca checkboxes no load. O
    navegador envia esses valores; pelo HTTP precisamos aplica-los nos.
    """
    scripts = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", html or "", re.IGNORECASE | re.DOTALL))
    codigo = _sem_funcoes(scripts)
    valores = {}
    for nome, expressao in _ATRIBUI_VALOR_RE.findall(codigo):
        literais = re.findall(r""""([^"]*)"|'([^']*)'""", expressao)
        valores[nome] = "".join(duplas or simples for duplas, simples in literais)
    marcados = {nome: v.lower() == "true" for nome, v in _ATRIBUI_CHECKED_RE.findall(codigo)}
    return valores, marcados


_FRAME9_VALOR_RE = re.compile(
    r"""parent\.rotina\s*\.document\.all\s*\(\s*['"](\w+)['"]\s*\)\.value\s*=\s*([^;\n]+);"""
)
_LITERAL_RE = re.compile(r"""\s*(?:'[^']*'|"[^"]*"|-?\d+(?:[.,]\d+)?)\s*""")


def valores_do_frame9(texto: str) -> dict[str, str]:
    """Valores que a carga do frame 9 grava nos campos da rotina.

    Ex.: na 03.02.06 o frame 9 preenche portador 0..999, cliente 0..999999 etc.
    So valem atribuicoes feitas de literais ('18' + '/' + '11', 0, 999); um campo
    que tambem recebe uma expressao calculada no navegador fica de fora.
    """
    valores: dict[str, str] = {}
    calculados: set[str] = set()
    for nome, expressao in _FRAME9_VALOR_RE.findall(texto or ""):
        partes = expressao.split("+")
        if not all(_LITERAL_RE.fullmatch(parte) for parte in partes):
            calculados.add(nome)
            continue
        valores[nome] = "".join(parte.strip().strip("'\"") for parte in partes)
    return {nome: valor for nome, valor in valores.items() if nome not in calculados}


def aplicar_valores_do_frame9(form: Formulario, texto: str) -> None:
    for nome, valor in valores_do_frame9(texto).items():
        if nome in form.campos or nome in form.opcoes:
            form.campos[nome] = valor


def aplicar_valores_de_carga(form: Formulario, pagina: str) -> None:
    """Deixa o formulario como o navegador o deixaria depois de carregar a pagina."""
    valores, marcados = valores_de_carga(pagina)
    for nome, valor in valores.items():
        if nome in form.campos or nome in form.opcoes:
            form.campos[nome] = valor
    for nome, marcado in marcados.items():
        if nome not in form.checkboxes:
            continue
        if marcado:
            form.campos[nome] = form.checkboxes[nome]
        else:
            form.campos.pop(nome, None)
