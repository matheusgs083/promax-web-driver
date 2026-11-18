"""Liga o cliente HTTP ao orquestrador de relatorios, no lugar das paginas do Edge.

O orquestrador continua igual: chama iniciar_sessao/encerrar_sessao e as tarefas
de cada rotina. Quando o grupo esta habilitado em PROMAX_HTTP_GRUPOS, as tarefas
usam gerar_relatorio_http, que grava os CSVs na mesma pasta intermediaria e com os
mesmos nomes da versao Edge (<nome>_<codigo da unidade>.csv), e anota o tracker
com os mesmos status. Renomeador, repescagem e publicacao nao percebem diferenca.
"""
from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from promax_http.cliente import ClientePromax, Rotina
from promax_http.erros import PromaxHttpErro, RelatorioSemConteudo
from promax_http import ph
from promax_http.dvs import BuscaDvs
from promax_http.transporte import Transporte


def grupos_http() -> set[str]:
    return {g.strip().lower() for g in os.getenv("PROMAX_HTTP_GRUPOS", "").split(",") if g.strip()}


def rotinas_em_http(grupo: str, rotinas: list[str], rotinas_suportadas: set[str]) -> set[str]:
    """Rotinas do grupo que vao por HTTP: o grupo precisa estar em PROMAX_HTTP_GRUPOS
    e a rotina precisa ter receita. As demais continuam no Edge."""
    if grupo.lower() not in grupos_http():
        return set()
    return {rotina for rotina in rotinas if rotina in rotinas_suportadas}


@dataclass
class SessaoHttp:
    settings: object
    logger: object
    pasta_rastro: Path
    unidade_login: str | None = None
    cliente: ClientePromax | None = field(default=None, init=False)

    def iniciar(self) -> None:
        self.encerrar()
        rastro = self.pasta_rastro / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cliente = ClientePromax(
            self.settings.promax_url, transporte=Transporte(pasta_rastro=rastro), logger=self.logger
        )
        self.logger.info(">>> Iniciando sessao HTTP no Promax (sem navegador)...")
        # Como o login do Edge: a unidade configurada e so preferencia.
        self.cliente.login(self.settings.promax_user, self.settings.promax_pass, unidade_preferida=self.unidade_login)

    def encerrar(self) -> None:
        if self.cliente is None:
            return
        try:
            self.cliente.logoff()
        except Exception as exc:  # o logoff e cortesia; a sessao expira sozinha no servidor
            self.logger.debug("Logoff HTTP falhou: %s", exc)
        self.cliente = None


@dataclass(frozen=True)
class PedidoRelatorio:
    rotina: str
    tracker_name: str
    subpasta: str
    nome_arquivo: str
    campos: dict[str, str | None]
    # Postbacks da tela antes do Visualizar e opcao do Visualizar, quando o botao
    # nao chama Visualizar() direto (ex.: 15.05.01).
    passos_previos: tuple[str, ...] = ()
    opcao_visualizar: str | None = None
    # Nome exato por unidade (ex.: Liga: "03.02.24_PATOS_OUT.csv"). Sem ele vale o
    # padrao do loop_unidades: <nome_arquivo>_<codigo>.csv.
    nome_por_unidade: Callable[[str], str] | None = None


@dataclass(frozen=True)
class PedidoRelatorioPh:
    """Rotina de tela PH: uma geracao por pedido. Sem unidade, usa a da sessao."""

    rotina: str
    tracker_name: str
    subpasta: str
    nome_arquivo: str
    csv: ph.PedidoCsvPh
    marca_tela: str  # id que prova que o formulario da tela carregou (ex.: btnGerarCSV)
    unidade: str | None = None


@dataclass(frozen=True)
class PedidoRelatorioPdf:
    """Rotina que gera PDF pelo frame 9 (sem Visualizar/CSV), ex.: 03.02.06."""

    rotina: str
    tracker_name: str
    subpasta: str
    nome_arquivo: str  # base; vira <base>_<codigo da unidade>.pdf, como no loop_unidades
    campos: dict[str, str | None]
    opcao: str


@dataclass(frozen=True)
class PedidoArquivoDvs:
    """Rotina que grava arquivo no DVS do servidor (03.08.05, 17.06): Visualizar
    por unidade e depois buscar o arquivo (ver promax_http/dvs.py)."""

    rotina: str
    tracker_name: str
    subpasta: str
    campos_da_unidade: Callable[[str], dict[str, str | None]]
    nome_final_da_unidade: Callable[[str], str]
    # (busca, unidade, instante do Visualizar) -> (origem, conteudo) ou None
    localizar: Callable[[BuscaDvs, str, float], tuple[str, bytes] | None]
    unidade_permitida: Callable[[str], bool] = lambda unidade: True


def downloads_simultaneos() -> int:
    """PROMAX_HTTP_DOWNLOADS (padrao 4), como a fila de downloads do robo do Edge."""
    try:
        return max(1, int(os.getenv("PROMAX_HTTP_DOWNLOADS", "4")))
    except ValueError:
        return 4


def gerar_relatorio_http(
    sessao: SessaoHttp,
    pedido: PedidoRelatorio,
    *,
    unidades_alvo: list[str] | None,
    pasta_base: Path,
    tracker,
    logger,
) -> ExecutionResult:
    """Equivalente HTTP de RotinaPage.loop_unidades + fila de downloads do Edge.

    Uma sessao e uma janela de rotina, como o robo atual: para cada unidade a
    janela troca a unidade e Visualiza; a exportacao e o download vao para uma
    fila em segundo plano (ate PROMAX_HTTP_DOWNLOADS ao mesmo tempo) e a janela
    ja segue para a proxima unidade. O tracker so anota SUCESSO quando o arquivo
    foi baixado de fato.
    """
    if sessao.cliente is None:
        sessao.iniciar()
    cliente = sessao.cliente
    rotina = cliente.abrir_rotina(pedido.rotina)
    situacoes: list = []
    inicio = time.time()
    try:
        unidades = _filtrar_unidades(rotina, unidades_alvo)
        if not unidades:
            return ExecutionResult(
                status=ExecutionStatus.BUSINESS_FAILURE,
                message=f"Nenhuma unidade alvo {unidades_alvo} foi encontrada na rotina {pedido.rotina}",
            )
        base, ext = os.path.splitext(pedido.nome_arquivo)
        with ThreadPoolExecutor(max_workers=downloads_simultaneos(), thread_name_prefix="promax-http") as fila:
            for indice, codigo in enumerate(unidades, start=1):
                logger.info("===> [%d/%d] %s unidade %s (HTTP)", indice, len(unidades), pedido.tracker_name, codigo)
                nome = pedido.nome_por_unidade(codigo) if pedido.nome_por_unidade else f"{base}_{codigo}{ext or '.csv'}"
                destino = pasta_base / pedido.subpasta / nome
                t0 = time.time()
                try:
                    rotina = cliente.trocar_unidade(rotina, codigo)
                    exportacao = cliente.preparar_exportacao(
                        rotina,
                        pedido.campos,
                        passos_previos=pedido.passos_previos,
                        opcao_visualizar=pedido.opcao_visualizar,
                    )
                except RelatorioSemConteudo as exc:
                    tracker.anotar(pedido.tracker_name, codigo, "SEM CONTEUDO", str(exc), time.time() - t0)
                    situacoes.append("sem_conteudo")
                    continue
                except PromaxHttpErro as exc:
                    logger.error("Unidade %s falhou (HTTP): %s", codigo, exc)
                    tracker.anotar(pedido.tracker_name, codigo, "ERRO SISTEMA", str(exc), time.time() - t0)
                    situacoes.append("falha")
                    continue
                situacoes.append(
                    fila.submit(_concluir, cliente, exportacao, destino, pedido, codigo, t0, tracker, logger)
                )
                logger.info("Unidade %s na fila de download; seguindo para a proxima.", codigo)
            situacoes = [s.result() if hasattr(s, "result") else s for s in situacoes]
    finally:
        try:
            cliente.fechar_rotina(rotina)
        except PromaxHttpErro as exc:
            logger.debug("Fechamento da rotina HTTP falhou: %s", exc)
    logger.info("%s concluida em %.0fs.", pedido.tracker_name, time.time() - inicio)

    contagem = {"sucesso": 0, "sem_conteudo": 0, "falha": 0}
    for situacao in situacoes:
        contagem[situacao] += 1
    return _consolidar(contagem, len(unidades))


def _concluir(cliente, exportacao, destino, pedido, codigo, inicio, tracker, logger) -> str:
    try:
        arquivo = cliente.concluir_exportacao(exportacao, destino)
    except RelatorioSemConteudo as exc:
        tracker.anotar(pedido.tracker_name, codigo, "SEM CONTEUDO", str(exc), time.time() - inicio)
        return "sem_conteudo"
    except PromaxHttpErro as exc:
        logger.error("Download da unidade %s falhou (HTTP): %s", codigo, exc)
        tracker.anotar(pedido.tracker_name, codigo, "ERRO SISTEMA", str(exc), time.time() - inicio)
        return "falha"
    detalhe = f"Download HTTP validado ({arquivo.stat().st_size} bytes)"
    tracker.anotar(pedido.tracker_name, codigo, "SUCESSO", detalhe, time.time() - inicio)
    logger.info("Unidade %s baixada em %.0fs: %s", codigo, time.time() - inicio, arquivo.name)
    return "sucesso"


def _filtrar_unidades(rotina: Rotina, unidades_alvo: list[str] | None) -> list[str]:
    disponiveis = [o.valor for o in rotina.unidades]
    if not unidades_alvo:
        return disponiveis
    alvos = {str(u).strip() for u in unidades_alvo}
    return [codigo for codigo in disponiveis if codigo in alvos]


def _consolidar(contagem: dict[str, int], total: int) -> ExecutionResult:
    """Mesmas regras de RotinaPage.loop_unidades, para o orquestrador decidir igual."""
    sucesso, vazio, falha = contagem["sucesso"], contagem["sem_conteudo"], contagem["falha"]
    if falha == 0:
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Execucao concluida: {sucesso}/{total} unidade(s) com relatorio e {vazio} sem conteudo",
            retry=False,
        )
    if sucesso > 0:
        return ExecutionResult(
            status=ExecutionStatus.PARTIAL_SUCCESS,
            message=f"Execucao parcial: {sucesso}/{total} unidade(s) com sucesso e {falha} falha(s) tecnica(s)",
            retry=True,
        )
    return ExecutionResult(
        status=ExecutionStatus.TECHNICAL_FAILURE,
        message=f"Nenhuma unidade processada com sucesso. {falha} falha(s) tecnica(s)",
        retry=True,
    )


def gerar_relatorio_ph_http(
    sessao: SessaoHttp,
    pedido: PedidoRelatorioPh,
    *,
    pasta_base: Path,
    tracker,
    logger,
) -> ExecutionResult:
    """Equivalente HTTP das paginas Edge das telas PH (ex.: Relatorio0105070402Page):
    abre a tela, aciona o Gerar CSV e baixa o arquivo devolvido."""
    if sessao.cliente is None:
        sessao.iniciar()
    cliente = sessao.cliente
    rotina = cliente.abrir_rotina(pedido.rotina)
    destino = pasta_base / pedido.subpasta / pedido.nome_arquivo
    rotulo = pedido.unidade or "TODAS"
    inicio = time.time()
    contagem = {"sucesso": 0, "sem_conteudo": 0, "falha": 0}
    try:
        if pedido.unidade:
            rotina = ph.trocar_unidade(cliente, rotina, pedido.unidade)
        ph.carregar_tela(cliente, rotina, pedido.marca_tela)
        arquivo = ph.gerar_csv(cliente, rotina, pedido.csv, destino)
    except RelatorioSemConteudo as exc:
        tracker.anotar(pedido.tracker_name, rotulo, "SEM CONTEUDO", str(exc), time.time() - inicio)
        contagem["sem_conteudo"] += 1
    except PromaxHttpErro as exc:
        logger.error("%s falhou (HTTP): %s", pedido.tracker_name, exc)
        tracker.anotar(pedido.tracker_name, rotulo, "ERRO SISTEMA", str(exc), time.time() - inicio)
        contagem["falha"] += 1
    else:
        detalhe = f"Download HTTP validado ({arquivo.stat().st_size} bytes)"
        tracker.anotar(pedido.tracker_name, rotulo, "SUCESSO", detalhe, time.time() - inicio)
        contagem["sucesso"] += 1
    finally:
        try:
            cliente.fechar_rotina(rotina)
        except PromaxHttpErro as exc:
            logger.debug("Fechamento da rotina HTTP falhou: %s", exc)
    logger.info("%s concluida em %.0fs.", pedido.tracker_name, time.time() - inicio)
    return _consolidar(contagem, 1)


def gerar_pdf_http(
    sessao: SessaoHttp,
    pedido: PedidoRelatorioPdf,
    *,
    unidades_alvo: list[str] | None,
    pasta_base: Path,
    tracker,
    logger,
) -> ExecutionResult:
    """Equivalente HTTP do loop_unidades das rotinas de PDF: troca a unidade,
    gera o PDF e baixa, uma unidade por vez (a geracao ocupa a janela da rotina)."""
    if sessao.cliente is None:
        sessao.iniciar()
    cliente = sessao.cliente
    rotina = cliente.abrir_rotina(pedido.rotina)
    contagem = {"sucesso": 0, "sem_conteudo": 0, "falha": 0}
    inicio = time.time()
    try:
        unidades = _filtrar_unidades(rotina, unidades_alvo)
        if not unidades:
            return ExecutionResult(
                status=ExecutionStatus.BUSINESS_FAILURE,
                message=f"Nenhuma unidade alvo {unidades_alvo} foi encontrada na rotina {pedido.rotina}",
            )
        base, _ = os.path.splitext(pedido.nome_arquivo)
        for indice, codigo in enumerate(unidades, start=1):
            logger.info("===> [%d/%d] %s unidade %s (HTTP)", indice, len(unidades), pedido.tracker_name, codigo)
            destino = pasta_base / pedido.subpasta / f"{base}_{codigo}.pdf"
            t0 = time.time()
            try:
                rotina = cliente.trocar_unidade(rotina, codigo)
                arquivo = cliente.gerar_pdf_frame9(rotina, pedido.campos, opcao=pedido.opcao, destino=destino)
            except RelatorioSemConteudo as exc:
                tracker.anotar(pedido.tracker_name, codigo, "SEM CONTEUDO", str(exc), time.time() - t0)
                contagem["sem_conteudo"] += 1
                continue
            except PromaxHttpErro as exc:
                logger.error("Unidade %s falhou (HTTP): %s", codigo, exc)
                tracker.anotar(pedido.tracker_name, codigo, "ERRO SISTEMA", str(exc), time.time() - t0)
                contagem["falha"] += 1
                continue
            detalhe = f"PDF HTTP validado ({arquivo.stat().st_size} bytes)"
            tracker.anotar(pedido.tracker_name, codigo, "SUCESSO", detalhe, time.time() - t0)
            contagem["sucesso"] += 1
    finally:
        try:
            cliente.fechar_rotina(rotina)
        except PromaxHttpErro as exc:
            logger.debug("Fechamento da rotina HTTP falhou: %s", exc)
    logger.info("%s concluida em %.0fs.", pedido.tracker_name, time.time() - inicio)
    return _consolidar(contagem, len(unidades))


def gerar_arquivo_dvs_http(
    sessao: SessaoHttp,
    pedido: PedidoArquivoDvs,
    *,
    unidades_alvo: list[str] | None,
    pasta_base: Path,
    tracker,
    logger,
    espera: float = 120,
    intervalo: float = 5,
) -> ExecutionResult:
    """Equivalente HTTP das paginas Edge da 03.08.05/17.06: por unidade, troca a
    unidade, Visualiza e espera o arquivo aparecer no DVS."""
    if sessao.cliente is None:
        sessao.iniciar()
    cliente = sessao.cliente
    # Timeout curto na busca: um dos caminhos HTTP (porta 8080) pode nem responder.
    busca = BuscaDvs(Transporte(timeout=20), sessao.settings.promax_url, logger)
    rotina = cliente.abrir_rotina(pedido.rotina)
    contagem = {"sucesso": 0, "sem_conteudo": 0, "falha": 0}
    inicio_total = time.time()
    unidades: list[str] = []
    try:
        unidades = [u for u in _filtrar_unidades(rotina, unidades_alvo) if pedido.unidade_permitida(u)]
        if not unidades:
            return ExecutionResult(
                status=ExecutionStatus.BUSINESS_FAILURE,
                message=f"Nenhuma unidade alvo {unidades_alvo} disponivel para a rotina {pedido.rotina}",
            )
        for indice, codigo in enumerate(unidades, start=1):
            logger.info("===> [%d/%d] %s unidade %s (HTTP)", indice, len(unidades), pedido.tracker_name, codigo)
            t0 = time.time()
            try:
                rotina = cliente.trocar_unidade(rotina, codigo)
                instante = time.time()
                cliente.visualizar(rotina, pedido.campos_da_unidade(codigo))
                achado = pedido.localizar(busca, codigo, instante)
                while achado is None and time.time() - instante < espera:
                    logger.info("... aguardando o arquivo da %s (%s) no DVS", pedido.rotina, codigo)
                    time.sleep(intervalo)
                    achado = pedido.localizar(busca, codigo, instante)
                if achado is None:
                    raise PromaxHttpErro(f"Arquivo da {pedido.rotina} ({codigo}) nao apareceu no DVS em {espera:.0f}s")
            except RelatorioSemConteudo as exc:
                tracker.anotar(pedido.tracker_name, codigo, "SEM CONTEUDO", str(exc), time.time() - t0)
                contagem["sem_conteudo"] += 1
                continue
            except PromaxHttpErro as exc:
                logger.error("Unidade %s falhou (HTTP): %s", codigo, exc)
                tracker.anotar(pedido.tracker_name, codigo, "ERRO SISTEMA", str(exc), time.time() - t0)
                contagem["falha"] += 1
                continue
            origem, conteudo = achado
            destino = pasta_base / pedido.subpasta / pedido.nome_final_da_unidade(codigo)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(conteudo)
            logger.info("Arquivo da %s (%s) salvo: %s <- %s", pedido.rotina, codigo, destino.name, origem)
            tracker.anotar(pedido.tracker_name, codigo, "SUCESSO", f"DVS {origem} ({len(conteudo)} bytes)", time.time() - t0)
            contagem["sucesso"] += 1
    finally:
        try:
            cliente.fechar_rotina(rotina)
        except PromaxHttpErro as exc:
            logger.debug("Fechamento da rotina HTTP falhou: %s", exc)
    logger.info("%s concluida em %.0fs.", pedido.tracker_name, time.time() - inicio_total)
    return _consolidar(contagem, len(unidades))
