from __future__ import annotations

from typing import Any, Iterable

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


class Processo020301Grade020304Page(RotinaPage):
    """02.03.01: lança produtos em uma grade que alimenta o estoque 02.03.04."""

    FRAME_ROTINA = 1

    @staticmethod
    def _numero(value: Any, field: str) -> str:
        text = str("" if value is None else value).strip().replace(".0", "")
        if not text.isdigit():
            raise ValueError(f"{field} deve ser numérico e informado.")
        return text

    @classmethod
    def normalizar(cls, grade: Any, itens: Iterable[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        grade = cls._numero(grade, "Grade")
        normalizados: list[dict[str, Any]] = []
        for item in itens:
            produto = cls._numero(item.get("produto") or item.get("codigo") or item.get("item"), "Produto")
            quantidade_bruta = next(
                (item[campo] for campo in ("quantidade", "fabricado_outra_unidade", "natureza2") if campo in item),
                None,
            )
            quantidade = cls._numero(quantidade_bruta, "Quantidade")
            if int(quantidade) < 0:
                raise ValueError("Quantidade nao pode ser negativa.")
            normalizados.append({"produto": produto, "quantidade": quantidade, "source_row": item.get("source_row")})
        if not normalizados:
            raise ValueError("Informe ao menos um produto para a grade.")
        return grade, normalizados

    def lancar(self, *, grade: Any, itens: Iterable[dict[str, Any]]) -> ExecutionResult:
        try:
            grade, itens = self.normalizar(grade, itens)
            auditoria: list[dict[str, Any]] = []
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            ok, mensagem = self.preencher_campo_com_gatilho("nrGradeArmazem", grade.zfill(2), "CarregarGrade();")
            if not ok:
                return self._falha("grade", mensagem, itens=itens, auditoria=auditoria)
            for indice, item in enumerate(itens, start=1):
                self.logger.info("020301 auditoria: produto=%s linha=%s iniciando", item["produto"], item.get("source_row") or indice)
                ok, mensagem = self.preencher_campo_com_gatilho("codigoProduto", item["produto"], "CarregarProduto();")
                if not ok:
                    return self._falha_item(item, indice, mensagem, itens, auditoria)
                self.js_set_input_by_name("natureza2", item["quantidade"])
                ok, mensagem = self.executar_gatilho_e_aguardar("AdicionaSaldo();")
                if not ok:
                    return self._falha_item(item, indice, mensagem, itens, auditoria)
                ok, mensagem = self.executar_gatilho_e_aguardar("Salvar();")
                if not ok:
                    return self._falha_item(item, indice, mensagem, itens, auditoria)
                auditoria.append(self._audit_row(item, "LANCADO", "Salvo no Promax."))
                self.logger.info("020301 auditoria: produto=%s linha=%s lançado", item["produto"], item.get("source_row") or indice)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message="Grade lançada para o estoque 02.03.04.", metadata={"grade": grade, "itens": len(itens), "failed_items": [], "item_audit": auditoria})
        except ValueError as exc:
            return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=str(exc), retry=False)
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha na rotina 02.03.01: {exc}")

    def _falha_item(self, item: dict[str, Any], indice: int, mensagem: Any, itens: list[dict[str, Any]], auditoria: list[dict[str, Any]]) -> ExecutionResult:
        auditoria.append(self._audit_row(item, "FALHOU", str(mensagem)))
        auditoria.extend(self._audit_row(restante, "NAO_EXECUTADO", "Não executado após falha anterior.") for restante in itens[indice:])
        return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=f"Falha ao lançar produto {item['produto']}: {mensagem}", metadata={"failed_items": [{"source_row": item.get("source_row") or indice, "produto": item["produto"], "reason": str(mensagem)}], "item_audit": auditoria})

    @staticmethod
    def _falha(etapa: str, mensagem: Any, *, itens: list[dict[str, Any]], auditoria: list[dict[str, Any]]) -> ExecutionResult:
        auditoria.extend(Processo020301Grade020304Page._audit_row(item, "NAO_EXECUTADO", f"Não executado: falha ao carregar {etapa}.") for item in itens)
        return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=f"Falha ao processar {etapa}: {mensagem or 'Sem confirmação do Promax.'}", metadata={"failed_items": [], "item_audit": auditoria})

    @staticmethod
    def _audit_row(item: dict[str, Any], status: str, detalhe: str) -> dict[str, Any]:
        return {"source_row": item.get("source_row"), "produto": item["produto"], "quantidade": item["quantidade"], "status": status, "detail": detalhe}
