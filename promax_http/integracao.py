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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from promax_http.cliente import ClientePromax, Rotina
from promax_http.erros import PromaxHttpErro, RelatorioSemConteudo
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
        self.cliente.login(self.settings.promax_user, self.settings.promax_pass, unidade=self.unidade_login)

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
    campos: dict[str, str]


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
                destino = pasta_base / pedido.subpasta / f"{base}_{codigo}{ext or '.csv'}"
                t0 = time.time()
                try:
                    rotina = cliente.trocar_unidade(rotina, codigo)
                    exportacao = cliente.preparar_exportacao(rotina, pedido.campos)
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
