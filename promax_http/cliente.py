"""Login, abertura de rotina, troca de unidade e exportacao de CSV por HTTP.

Fluxo observado nas capturas mitmproxy (logs/mitm/030302_ie_*.mitm):

1. POST ?ppopcao=1 com Usuario/Senha            -> tela de unidade com token de senha
2. POST ?ppopcao=1 com ppopcao=2, SessionID novo -> menu (sessao aberta)
3. POST ppopcao=6 call=PP00101 MenuID=<codigo>   -> JSON com o programa da rotina
4. GET  ppopcao=7 call=<MenuID> SubSessionID=<novo> -> frameset da rotina
5. GET  frames top_rotina (ppopcao=8), rotina (frame=0) e bottom_rotina
6. POST no frame 9 da rotina com os campos do form1 -> resposta em JavaScript
7. GET  ppopcao=10 fecha a sub-sessao da rotina

Nao ha cookies: a sessao vive nos parametros SessionID e SubSessionID.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit

from promax_http import alertas as classificar
from promax_http import html
from promax_http.erros import (
    ExportacaoNaoEntendida,
    LoginRecusado,
    PromaxHttpErro,
    RelatorioSemConteudo,
    SemPermissao,
)
from promax_http.ids import gerar_id_troca_unidade, gerar_session_id
from promax_http.transporte import Resposta, Transporte

OPCAO_EXPORTAR = "88"
OPCAO_RELAT_CSV = "3"
_FUNCAO_ONCLICK_RE = re.compile(r"(\w+)\s*\(")


@dataclass(frozen=True)
class ExportacaoPreparada:
    url: str
    campos: dict[str, str]


@dataclass
class Rotina:
    codigo: str
    menu_id: str
    programa: str
    sub_session_id: str
    url_rotina: str
    url_frame9: str
    form: html.Formulario
    html_rotina: str
    html_topo: str
    unidades: list[html.Opcao] = field(default_factory=list)

    @property
    def unidade_ativa(self) -> str | None:
        return html.unidade_ativa(self.html_topo)


class ClientePromax:
    def __init__(self, url_promax: str, *, transporte: Transporte, logger=None) -> None:
        partes = urlsplit(url_promax)
        self.base = f"{partes.scheme}://{partes.netloc}/pw/cgi-bin/PP00100.exe"
        self.http = transporte
        self.logger = logger
        self.session_id: str | None = None
        self.usuario: str | None = None
        self.alertas_login: list[str] = []

    # ------------------------------------------------------------------ login
    def login(self, usuario: str, senha: str, unidade: str | None = None) -> str:
        self._log("Conectando ao Promax em %s ...", self.base)
        self.http.get(f"{self.base}?ppopcao=1")
        r1 = self.http.post(
            f"{self.base}?ppopcao=1",
            {
                "SessionID": "", "ppopcao": "1", "opcaomenu": "", "call": "", "versaoBase": "12.22",
                "Animate": "0", "animpath": "", "ssoLogin": "",
                "Usuario": usuario, "Senha": senha, "cmdConfirma": "Confirma",
            },
        )
        try:
            form = html.formulario(r1.texto, "frmLogin")
        except ValueError as exc:
            raise LoginRecusado(f"Resposta inesperada no login: {html.alertas(r1.texto)}") from exc
        if form.campos.get("ppopcao") != "2":
            recusa = classificar.contem(html.alertas(r1.texto), classificar.LOGIN_RECUSADO)
            raise LoginRecusado(recusa or f"Login nao avancou: {html.alertas(r1.texto) or 'sem alerta'}")

        codigo_unidade = self._resolver_unidade(form.opcoes.get("unidade", []), unidade)
        self._log("Usuario aceito. Entrando na unidade %s ...", codigo_unidade)
        campos = dict(form.campos)
        self.session_id = gerar_session_id()
        campos.update({"SessionID": self.session_id, "unidade": codigo_unidade, "cmdConfirma": "Confirma"})
        r2 = self.http.post(f"{self.base}?ppopcao=1", campos)

        if f"value={self.session_id}" not in r2.texto.replace('"', ""):
            raise LoginRecusado(f"Menu nao abriu apos escolher a unidade: {html.alertas(r2.texto) or 'sem alerta'}")
        self.usuario = usuario
        self.alertas_login = html.alertas(r2.texto)
        self._log("Login HTTP ok (unidade %s). Alertas: %s", codigo_unidade, self.alertas_login)
        self.http.post(self.base, {"SessionID": self.session_id, "ppopcao": "3"})
        return codigo_unidade

    def logoff(self) -> None:
        if not self.session_id:
            return
        try:
            self.http.post(
                self.base,
                {"Usuario": self.usuario or "", "SessionID": self.session_id, "logoff": "1", "ppopcao": "1"},
            )
        finally:
            self.session_id = None

    # ---------------------------------------------------------------- rotinas
    def abrir_rotina(
        self, codigo: str, *, menu_id: str | None = None, sub_session_id: str | None = None
    ) -> Rotina:
        """Abre a rotina numa sub-sessao nova, ou numa existente (ex.: a sub-sessao em
        que a tela PH acabou de trocar de unidade; a unidade fica presa a ela)."""
        self._exigir_sessao()
        self._log("Procurando a rotina %s no menu ...", codigo)
        menu_id, programa = self._localizar_rotina(codigo, menu_id)
        self._log("Abrindo a rotina %s (programa %s) ...", codigo, programa)
        sub = sub_session_id or gerar_session_id()
        url = f"{self.base}?SessionID={self.session_id}&ppopcao=7&call={menu_id}&SubSessionID={sub}"
        return self._carregar_frames(codigo, menu_id, programa, sub, self.http.get(url))

    def trocar_unidade(self, rotina: Rotina, unidade: str) -> Rotina:
        codigo = self._resolver_unidade(rotina.unidades, unidade)
        if rotina.unidade_ativa == codigo:
            self._log("Unidade %s ja ativa na rotina.", codigo)
            return rotina
        self._log("Trocando a unidade da rotina para %s ...", codigo)
        nova = self.reabrir_em_unidade(rotina, codigo)
        if nova.unidade_ativa != codigo:
            raise PromaxHttpErro(
                f"Unidade nao trocou: pedida {codigo}, ativa {nova.unidade_ativa}. Veja o rastro."
            )
        return nova

    def reabrir_em_unidade(self, rotina: Rotina, codigo: str) -> Rotina:
        """Pede a rotina de novo ja na unidade (changeUNB=A), como o combo de unidade
        do topo faz. O Promax responde com um SessionID novo, preso a essa unidade.
        Serve tambem para as telas PH. Quem chama confere a unidade da tela devolvida."""
        resposta = self.http.post(
            self.base,
            {
                "SessionID": gerar_id_troca_unidade(), "SubSessionID": rotina.sub_session_id,
                "ppopcao": "7", "call": rotina.menu_id, "changeUNB": "A", "unidade": codigo,
                "ssprx": "00", "parMF": "",
            },
        )
        falha = classificar.contem(html.alertas(resposta.texto), classificar.SEM_PERMISSAO)
        if falha:
            raise SemPermissao(f"Troca para a unidade {codigo} recusada: {falha}")
        return self._carregar_frames(rotina.codigo, rotina.menu_id, rotina.programa, rotina.sub_session_id, resposta)

    def fechar_rotina(self, rotina: Rotina) -> None:
        self.http.get(f"{self.base}?SessionID={self.session_id}&SubSessionID={rotina.sub_session_id}&ppopcao=10")

    # ------------------------------------------------------------- exportacao
    def exportar_csv(
        self, rotina: Rotina, campos: dict[str, str | None], destino: Path, **opcoes
    ) -> Path:
        """Visualiza e exporta na hora (uma etapa depois da outra)."""
        return self.concluir_exportacao(self.preparar_exportacao(rotina, campos, **opcoes), destino)

    def preparar_exportacao(
        self,
        rotina: Rotina,
        campos: dict[str, str | None],
        *,
        passos_previos: tuple[str, ...] = (),
        opcao_visualizar: str | None = None,
    ) -> "ExportacaoPreparada":
        """Etapa que precisa da janela da rotina: preenche e Visualiza.

        Devolve o pedido de exportacao pronto (URL + campos da tela de resultado,
        com SessionID/SubSessionID daquele momento). Como no robo do Edge, ele
        pode ser concluido em segundo plano enquanto a janela ja vai para a
        proxima unidade.
        """
        # None nos campos da receita significa "nao enviar" (ex.: checkbox desmarcado).
        valores = {k: v for k, v in {**rotina.form.campos, **campos}.items() if v is not None}
        # Postbacks que a tela faz no frame 9 antes do Visualizar (ex.: a 15.05.01
        # carrega listas e valida selecoes com opcao=2..5).
        for opcao in passos_previos:
            self._log("Postback da tela (opcao=%s) ...", opcao)
            self._falhar_por_alerta(self._enviar_frame9(rotina, {**valores, "opcao": opcao}))
        opcao_visualizar = opcao_visualizar or _opcao_do_botao(rotina.html_rotina, rotina.form, "BotVisualizar")
        if not opcao_visualizar:
            # Rotina sem Visualizar: exporta direto pelo frame 9.
            return ExportacaoPreparada(
                url=rotina.url_frame9,
                campos={
                    **valores, "frame": "9", "SessionID": self.session_id,
                    "SubSessionID": rotina.sub_session_id, "ppopcao": "00", "call": rotina.programa,
                    "opcao": OPCAO_EXPORTAR, "opcaorelat": OPCAO_RELAT_CSV,
                },
            )

        tela = self._visualizar(rotina, valores, opcao_visualizar)
        form_resultado = _form_de_exportacao(tela.texto)
        if form_resultado is None:
            raise ExportacaoNaoEntendida(
                f"Visualizar nao trouxe a tela com GeraExcel. Alertas: {html.alertas(tela.texto)}. Envie a pasta de rastro."
            )
        url = tela.url if not form_resultado.action else urljoin(tela.url, form_resultado.action)
        return ExportacaoPreparada(
            url=url, campos={**form_resultado.campos, "opcao": OPCAO_EXPORTAR, "opcaorelat": OPCAO_RELAT_CSV}
        )

    def visualizar(self, rotina: Rotina, campos: dict[str, str | None]) -> Resposta:
        """So o Visualizar, para rotinas cujo resultado nao e a tela de exportacao
        (ex.: 03.08.05 e 17.06 gravam um arquivo no DVS do servidor)."""
        valores = {k: v for k, v in {**rotina.form.campos, **campos}.items() if v is not None}
        opcao = _opcao_do_botao(rotina.html_rotina, rotina.form, "BotVisualizar") or "1"
        return self._visualizar(rotina, valores, opcao)

    def _visualizar(self, rotina: Rotina, valores: dict[str, str], opcao: str) -> Resposta:
        self._log("Visualizando o relatorio (o Promax pode demorar) ...")
        inicio = time.time()
        tela = self.http.post(rotina.url_rotina, {**valores, "opcao": opcao})
        self._log("Promax gerou o relatorio em %.0fs.", time.time() - inicio)
        self._falhar_por_alerta(tela)
        return tela

    def concluir_exportacao(self, exportacao: "ExportacaoPreparada", destino: Path) -> Path:
        """Pede o CSV e baixa. Nao usa a janela da rotina: pode rodar em paralelo."""
        self._log("Pedindo a exportacao em CSV: %s ...", destino.name)
        resposta = self.http.post(exportacao.url, exportacao.campos)
        arquivo = self._salvar_se_for_relatorio(resposta, destino)
        if arquivo:
            return arquivo
        self._falhar_por_alerta(resposta)
        raise ExportacaoNaoEntendida(
            f"A exportacao nao devolveu arquivo. Alertas: {html.alertas(resposta.texto)}. Envie a pasta de rastro."
        )

    def gerar_pdf_frame9(
        self,
        rotina: Rotina,
        campos: dict[str, str | None],
        *,
        opcao: str,
        destino: Path,
        espera: float = 600,
        intervalo: float = 5,
    ) -> Path:
        """Rotinas que geram PDF pelo frame 9 (ex.: 03.02.06 com opcao=4).

        Repete o EnviarFormulario() da tela e procura o link tmp/rels/*.pdf na
        resposta. Se o Promax so devolver o "processando", acompanha o XML de
        progresso que a tela consulta (DisplayLoopXML) ate o link aparecer.
        """
        valores = {k: v for k, v in {**rotina.form.campos, **campos}.items() if v is not None}
        self._log("Gerando o PDF da rotina %s (opcao=%s; o Promax pode demorar) ...", rotina.codigo, opcao)
        inicio = time.time()
        resposta = self._enviar_frame9(rotina, {**valores, "opcao": opcao})
        self._falhar_por_alerta(resposta)
        arquivo = self._baixar_pdf_citado(resposta, destino)
        if arquivo is None and _processo_terminou(resposta.texto):
            # displayLoop = 'FIM': o Promax ja encerrou e nao citou PDF nenhum.
            raise ExportacaoNaoEntendida(
                f"O Promax terminou a {rotina.codigo} sem gerar PDF. Alertas: {html.alertas(resposta.texto)}"
            )
        url_xml = _url_xml_progresso(rotina)
        while arquivo is None and url_xml and time.time() - inicio < espera:
            time.sleep(intervalo)
            progresso = self.http.get(url_xml)
            self._log("... PDF da %s: %s (%.0fs)", rotina.codigo, _chave_progresso(progresso.texto), time.time() - inicio)
            arquivo = self._baixar_pdf_citado(progresso, destino)
        if arquivo is None:
            raise ExportacaoNaoEntendida(
                f"O Promax nao entregou o PDF da {rotina.codigo} em {time.time() - inicio:.0f}s. "
                f"Alertas: {html.alertas(resposta.texto)}. Envie a pasta de rastro."
            )
        return arquivo

    def _baixar_pdf_citado(self, resposta: Resposta, destino: Path) -> Path | None:
        for url in reversed(html.urls_relatorio(resposta.texto, resposta.url)):
            if ".pdf" in url.lower():
                arquivo = self.baixar_arquivo(url, destino, tipo="pdf")
                if arquivo:
                    return arquivo
        return None

    # --------------------------------------------------------------- internos
    def _localizar_rotina(self, codigo: str, menu_id: str | None) -> tuple[str, str]:
        candidatos = [menu_id] if menu_id else list(dict.fromkeys(
            [codigo.ljust(12, "0"), codigo.ljust(11, "0"), codigo.ljust(10, "0"), codigo, codigo.ljust(14, "0")]
        ))
        for candidato in candidatos:
            r = self.http.post(
                self.base,
                {"SessionID": self.session_id, "ppopcao": "6", "call": "PP00101", "opcao": "1", "MenuID": candidato},
            )
            atalho = _ler_atalho(r.texto)
            if not atalho or not atalho.get("prg"):
                continue
            if atalho.get("permissao") not in (None, "", "00"):
                raise SemPermissao(
                    f"Rotina {codigo}: usuario sem permissao no Promax (codigo {atalho.get('permissao')})"
                )
            return candidato, atalho["prg"].split(".")[0]
        raise PromaxHttpErro(f"Rotina {codigo} nao encontrada no menu (tentei {candidatos}).")

    def _carregar_frames(self, codigo, menu_id, programa, sub, frameset: Resposta) -> Rotina:
        texto = frameset.texto
        session_id = _valor_campo(texto, "SessionID")
        if session_id and session_id != self.session_id:
            self._log("Promax trocou o SessionID: %s -> %s", self.session_id, session_id)
            self.session_id = session_id
        mapa = html.frames(texto, frameset.url)
        if "rotina" not in mapa and _eh_tela_ph(texto):
            rotina = _rotina_ph(codigo, menu_id, sub, frameset)
            sessao_ph = rotina.form.campos.get("SessionID")
            if sessao_ph and sessao_ph != self.session_id:
                self._log("Promax trocou o SessionID: %s -> %s", self.session_id, sessao_ph)
                self.session_id = sessao_ph
            return rotina
        if "rotina" not in mapa:
            falha = classificar.contem(html.alertas(texto), classificar.SEM_PERMISSAO)
            if falha:
                raise SemPermissao(f"Rotina {codigo}: {falha}")
            raise PromaxHttpErro(f"Frameset da rotina {codigo} sem frame 'rotina'. Alertas: {html.alertas(texto)}")

        topo = self.http.get(mapa["top_rotina"]).texto if "top_rotina" in mapa else ""
        pagina = self.http.get(mapa["rotina"])
        falha = classificar.contem(html.alertas(pagina.texto), classificar.SEM_PERMISSAO)
        if falha:
            raise SemPermissao(f"Rotina {codigo}: {falha}")
        url_frame9 = html.url_frame_inferior(pagina.texto, pagina.url)
        if "bottom_rotina" in mapa:
            self.http.get(mapa["bottom_rotina"])
        carga_frame9 = ""
        if url_frame9:
            carga_frame9 = self.http.get(url_frame9).texto
        else:
            url_frame9 = _montar_url_frame9(self.base, self.session_id, sub, pagina.texto)

        form = html.formulario(pagina.texto, "form1")
        html.aplicar_valores_de_carga(form, pagina.texto)
        # O frame 9 tambem preenche campos ao carregar (ex.: faixas da 03.02.06).
        html.aplicar_valores_do_frame9(form, carga_frame9)
        unidades = []
        for f in html.ler_formularios(topo):
            unidades = f.opcoes.get("unidade", []) or unidades
        return Rotina(
            codigo=codigo, menu_id=menu_id, programa=form.campos.get("call", programa), sub_session_id=sub,
            url_rotina=pagina.url, url_frame9=url_frame9, form=form, html_rotina=pagina.texto,
            html_topo=topo, unidades=unidades,
        )

    def _enviar_frame9(self, rotina: Rotina, campos: dict[str, str]) -> Resposta:
        valores = {
            **campos, "frame": "9", "SessionID": self.session_id,
            "SubSessionID": rotina.sub_session_id, "ppopcao": "00", "call": rotina.programa,
        }
        return self.http.post(rotina.url_frame9, valores)

    def _salvar_se_for_relatorio(self, resposta: Resposta, destino: Path) -> Path | None:
        if _parece_csv(resposta):
            return _gravar(destino, resposta.corpo)
        for url in reversed(html.urls_relatorio(resposta.texto, resposta.url)):
            # O link "<nome>.csv.inf" que o Promax abre e o proprio CSV.
            arquivo = self.baixar_arquivo(url, destino)
            if arquivo:
                return arquivo
        return None

    def baixar_arquivo(self, url: str, destino: Path, *, tipo: str = "csv") -> Path | None:
        """Baixa o arquivo gerado pelo Promax em partes, com progresso no log.
        Devolve None quando o servidor nao entrega um arquivo do tipo esperado (csv ou pdf)."""
        nome = url.split("?")[0].rsplit("/", 1)[-1]
        self._log("Baixando arquivo gerado: %s", nome)
        status, content_type, total = self.http.baixar(
            url,
            destino,
            ao_progredir=lambda baixado, segundos: self._log(
                "... %s: %.1f MB em %.0fs", nome, baixado / 1_048_576, segundos
            ),
        )
        parcial = destino.with_suffix(destino.suffix + ".parcial")
        confere = _arquivo_parece_pdf if tipo == "pdf" else _arquivo_parece_csv
        if status == 200 and confere(parcial, content_type):
            parcial.replace(destino)
            self._log("Arquivo salvo: %s (%.1f MB)", destino.name, total / 1_048_576)
            return destino
        parcial.unlink(missing_ok=True)
        self._log("Arquivo nao veio (HTTP %s, %d bytes).", status, total)
        return None

    def _falhar_por_alerta(self, resposta: Resposta) -> None:
        textos = html.alertas(resposta.texto)
        vazio = classificar.contem(textos, classificar.SEM_CONTEUDO)
        if vazio:
            raise RelatorioSemConteudo(vazio)
        bloqueio = classificar.contem(textos, classificar.SEM_PERMISSAO)
        if bloqueio:
            raise SemPermissao(bloqueio)
        erro = classificar.contem(textos, classificar.FALHA_GERACAO)
        if erro:
            raise ExportacaoNaoEntendida(f"Promax recusou a geracao: {erro}")

    def _resolver_unidade(self, opcoes: list[html.Opcao], unidade: str | None) -> str:
        if not opcoes:
            if unidade:
                return unidade
            raise PromaxHttpErro("Nenhuma unidade disponivel para escolher")
        if not unidade:
            return opcoes[0].valor
        alvo = classificar.normalizar(unidade)
        for o in opcoes:
            if o.valor == unidade or alvo in classificar.normalizar(o.texto):
                return o.valor
        raise PromaxHttpErro(f"Unidade '{unidade}' nao existe. Opcoes: {[o.texto for o in opcoes]}")

    def _exigir_sessao(self) -> None:
        if not self.session_id:
            raise PromaxHttpErro("Faca login antes de abrir rotinas")

    def _log(self, msg, *args) -> None:
        if self.logger:
            self.logger.info(msg, *args)


def _eh_tela_ph(texto: str) -> bool:
    """Programas PH (ex.: PH050094) sao telas unicas com jQuery/AJAX, sem frameset."""
    return bool(re.search(r'name="?formPadrao"?', texto, re.IGNORECASE))


def _rotina_ph(codigo: str, menu_id: str, sub: str, pagina: Resposta) -> Rotina:
    form = html.formulario(pagina.texto, "formPadrao")
    # A exportacao dessas telas usa AJAX (ppopcao=14) e ainda nao e suportada;
    # aqui so montamos a Rotina para captura e analise.
    return Rotina(
        codigo=codigo, menu_id=menu_id, programa=form.campos.get("call", ""), sub_session_id=sub,
        url_rotina=pagina.url, url_frame9="", form=form, html_rotina=pagina.texto, html_topo="", unidades=[],
    )


def _ler_atalho(texto: str) -> dict | None:
    # O JSON do Promax vem em ISO-8859-1 e as vezes com espacos estranhos; extraimos so o que importa.
    bloco = re.search(r'"atalho"\s*:\s*\[\s*\{(.*?)\}', texto, re.DOTALL)
    if not bloco:
        return None
    return dict(re.findall(r'"(\w+)"\s*:\s*"([^"]*)"', bloco.group(1)))


def _valor_campo(texto: str, nome: str) -> str | None:
    achado = re.search(rf'name={nome}\b[^>]*value="?([^"\s>]+)', texto, re.IGNORECASE)
    return achado.group(1) if achado else None


def _montar_url_frame9(base: str, session_id: str, sub: str, html_rotina: str) -> str:
    programa = _valor_campo(html_rotina, "call") or ""
    return f"{base}?" + urlencode(
        {"SessionID": session_id, "SubSessionID": sub, "ppopcao": "00", "call": programa, "frame": "9", "opcao": "1"}
    ) + "&"


def _opcao_do_botao(texto: str, form: html.Formulario, nome_botao: str) -> str | None:
    botao = form.botoes.get(nome_botao)
    onclick = (botao or {}).get("onclick", "")
    funcao = _FUNCAO_ONCLICK_RE.search(re.sub(r"^\s*return\s+", "", onclick))
    if not funcao:
        return None
    corpo = _corpo_funcao(texto, funcao.group(1))
    opcao = re.search(r"opcao\.value\s*=\s*['\"]?(\d+)", corpo or "")
    return opcao.group(1) if opcao else None


def _corpo_funcao(texto: str, nome: str) -> str | None:
    inicio = re.search(rf"function\s+{re.escape(nome)}\s*\([^)]*\)\s*\{{", texto)
    if not inicio:
        return None
    profundidade, i = 1, inicio.end()
    while i < len(texto) and profundidade:
        profundidade += {"{": 1, "}": -1}.get(texto[i], 0)
        i += 1
    return texto[inicio.end():i - 1]


def _form_de_exportacao(texto: str) -> html.Formulario | None:
    for form in html.ler_formularios(texto):
        nomes = {nome.lower() for nome in [*form.botoes, *form.campos]}
        if nomes & {"gerexecl", "geraexcel", "gerexcel"}:
            return form
    return None


def _parece_csv(resposta: Resposta) -> bool:
    if not resposta.corpo:
        return False
    inicio = resposta.corpo[:300].lstrip().lower()
    if "html" in resposta.content_type.lower() or inicio.startswith((b"<html", b"<!doctype", b"<script", b"<")):
        return False
    return b";" in inicio or b"," in inicio or b"\t" in inicio


def _arquivo_parece_pdf(caminho: Path, content_type: str) -> bool:
    if not caminho.is_file():
        return False
    with caminho.open("rb") as arquivo:
        return arquivo.read(5) == b"%PDF-"


_XML_PROGRESSO_RE = re.compile(r'"(\.\./tmp/work/[^"]+)"\s*\+\s*"\.xml"')


def _url_xml_progresso(rotina: Rotina) -> str | None:
    """DisplayLoopXML(): arqXML = "../tmp/work/<usuario>_<unidade>_<sub>" + ".xml"."""
    achado = _XML_PROGRESSO_RE.search(rotina.html_rotina)
    return urljoin(rotina.url_rotina, achado.group(1) + ".xml") if achado else None


def _processo_terminou(texto: str) -> bool:
    return bool(re.search(r"""all\s*\(\s*'displayLoop'\s*\)\.value\s*=\s*'FIM'""", texto or ""))


def _chave_progresso(texto: str) -> str:
    achado = re.search(r'chave\s*=\s*"([^"]*)"', texto or "")
    return achado.group(1) if achado else "aguardando"


def _arquivo_parece_csv(caminho: Path, content_type: str) -> bool:
    if not caminho.is_file():
        return False
    with caminho.open("rb") as arquivo:
        inicio = arquivo.read(300)
    return _parece_csv(Resposta(url="", status=200, content_type=content_type, corpo=inicio))


def _gravar(destino: Path, conteudo: bytes) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".parcial")
    temporario.write_bytes(conteudo)
    temporario.replace(destino)
    return destino

