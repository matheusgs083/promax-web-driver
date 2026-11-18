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


def gerar_relatorio_http(
    sessao: SessaoHttp,
    pedido: PedidoRelatorio,
    *,
    unidades_alvo: list[str] | None,
    pasta_base: Path,
    tracker,
    logger,
) -> ExecutionResult:
    """Equivalente HTTP de RotinaPage.loop_unidades + _fluxo_exportar_csv."""
    if sessao.cliente is None:
        sessao.iniciar()
    cliente = sessao.cliente
    rotina = cliente.abrir_rotina(pedido.rotina)
    try:
        unidades = _filtrar_unidades(rotina, unidades_alvo)
        if not unidades:
            return ExecutionResult(
                status=ExecutionStatus.BUSINESS_FAILURE,
                message=f"Nenhuma unidade alvo {unidades_alvo} foi encontrada na rotina {pedido.rotina}",
            )
        base, ext = os.path.splitext(pedido.nome_arquivo)
        ext = ext or ".csv"
        contagem = {"sucesso": 0, "sem_conteudo": 0, "falha": 0}

        for indice, codigo in enumerate(unidades, start=1):
            logger.info("===> [%d/%d] %s unidade %s (HTTP)", indice, len(unidades), pedido.tracker_name, codigo)
            inicio = time.time()
            destino = pasta_base / pedido.subpasta / f"{base}_{codigo}{ext}"
            try:
                rotina = cliente.trocar_unidade(rotina, codigo)
                arquivo = cliente.exportar_csv(rotina, pedido.campos, destino)
                detalhe = f"Download HTTP validado ({arquivo.stat().st_size} bytes)"
                tracker.anotar(pedido.tracker_name, codigo, "SUCESSO", detalhe, time.time() - inicio)
                contagem["sucesso"] += 1
            except RelatorioSemConteudo as exc:
                tracker.anotar(pedido.tracker_name, codigo, "SEM CONTEUDO", str(exc), time.time() - inicio)
                contagem["sem_conteudo"] += 1
            except PromaxHttpErro as exc:
                logger.error("Unidade %s falhou (HTTP): %s", codigo, exc)
                tracker.anotar(pedido.tracker_name, codigo, "ERRO SISTEMA", str(exc), time.time() - inicio)
                contagem["falha"] += 1
        return _consolidar(contagem, len(unidades))
    finally:
        try:
            cliente.fechar_rotina(rotina)
        except PromaxHttpErro as exc:
            logger.debug("Fechamento da rotina HTTP falhou: %s", exc)


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
