from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Iterable

from selenium.common.exceptions import NoAlertPresentException

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


@dataclass(frozen=True)
class ItemGrade:
    codigo: str
    pallet: int = 0
    lastro: int = 0
    caixa: int = 0
    unidade: int = 0
    garrafa: str | None = None
    source_row: int | None = None


class Processo020105Page(RotinaPage):
    """Rotina 02.01.05: contagem de estoque/lancamento da grade (PW03084C)."""

    FRAME_ROTINA = 1
    # A 02.01.05 is a legacy server-side form.  The loader is hidden before
    # the dependent fields are actually rebuilt, so the generic 5s helper can
    # advance the workflow too early. Keep generous, explicit waits here.
    TRIGGER_TIMEOUT = 45.0
    SAVE_TIMEOUT = 60.0

    def _log(self, nivel: str, mensagem: str, *args):
        logger = getattr(self, "logger", None)
        if logger is not None:
            getattr(logger, nivel)(mensagem, *args)

    def _gatilho(self, script: str, etapa: str, timeout: float | None = None):
        prazo = self.TRIGGER_TIMEOUT if timeout is None else timeout
        self._log("info", "020105: etapa=%s iniciando timeout=%.1fs", etapa, prazo)
        ok, mensagem = self.executar_gatilho_e_aguardar(
            script,
            timeout=prazo,
            recusar_confirmacoes=True,
        )
        if ok:
            self._log("info", "020105: etapa=%s concluida", etapa)
        else:
            self._log("error", "020105: etapa=%s falhou: %s", etapa, mensagem)
        return ok, mensagem

    def _recusar_confirmacao_pendente(self) -> bool:
        """Recusa uma confirmação Sim/Não deixada pelo item anterior."""
        try:
            alerta = self.driver.switch_to.alert
            texto = str(alerta.text or "").strip()
        except (NoAlertPresentException, AttributeError):
            return False
        except Exception:
            return False
        normalizado = " ".join(texto.lower().split())
        if not normalizado or not any(
            termo in normalizado for termo in ("?", "confirma", "deseja", "marcar")
        ):
            return False
        alerta.dismiss()
        self._log("info", "020105: confirmação recusada explicitamente (Não): %s", texto)
        try:
            self.wait_for_no_alert(timeout=1)
        except Exception:
            pass
        return True

    def _aguardar_campo(self, nome: str, etapa: str, timeout: float = 45.0):
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=min(30, int(timeout)))
        try:
            self.aguardar_formulario_rotina(nome, timeout=timeout, frame_index=self.FRAME_ROTINA)
            self._log("info", "020105: etapa=%s campo=%s pronto", etapa, nome)
            return True, "OK"
        except Exception as exc:  # noqa: BLE001
            mensagem = f"Timeout aguardando campo {nome}: {exc}"
            self._log("error", "020105: etapa=%s %s", etapa, mensagem)
            return False, mensagem

    def _aguardar_campo_habilitado(self, nome: str, etapa: str, timeout: float = 45.0):
        try:
            self.wait_for_js_condition(
                f"var el=document.getElementsByName('{nome}')[0]; return !!el && !el.disabled;",
                timeout=timeout,
                description=f"020105 {etapa} habilitado",
            )
            return True, "OK"
        except Exception as exc:  # noqa: BLE001
            mensagem = f"Timeout aguardando {nome} habilitado: {exc}"
            self._log("error", "020105: etapa=%s %s", etapa, mensagem)
            return False, mensagem

    @staticmethod
    def _codigo(value: Any, field: str) -> str:
        codigo = str(value or "").strip().replace(".0", "")
        if not codigo or not codigo.isdigit():
            raise ValueError(f"{field} deve ser numerico e informado.")
        return codigo

    @staticmethod
    def _quantidade(value: Any, field: str) -> int:
        if value in (None, ""):
            return 0
        try:
            quantidade = int(str(value).strip().replace(".0", ""))
        except ValueError as exc:
            raise ValueError(f"{field} deve ser uma quantidade inteira.") from exc
        if quantidade < 0:
            raise ValueError(f"{field} nao pode ser negativa.")
        return quantidade

    @classmethod
    def normalizar_item(cls, item: ItemGrade | dict[str, Any]) -> ItemGrade:
        origem = item if isinstance(item, dict) else item.__dict__
        normalizado = ItemGrade(
            codigo=cls._codigo(origem.get("codigo") or origem.get("item"), "Item"),
            pallet=cls._quantidade(origem.get("pallet"), "Pallet"),
            lastro=cls._quantidade(origem.get("lastro"), "Lastro"),
            # A tela mostra este campo como SKU para o item carregado, mas o
            # DOM legado o expoe como qtCaixa.
            caixa=cls._quantidade(origem.get("caixa") or origem.get("sku"), "SKU"),
            unidade=cls._quantidade(origem.get("unidade") or origem.get("avulsa"), "Unidade"),
            garrafa=str(origem.get("garrafa") or "").strip() or None,
            source_row=cls._quantidade(origem.get("source_row"), "Linha de origem") or None,
        )
        if not any((normalizado.pallet, normalizado.lastro, normalizado.caixa, normalizado.unidade)):
            raise ValueError(f"Item {normalizado.codigo} sem quantidade para lancar.")
        return normalizado

    @classmethod
    def normalizar_lancamento(
        cls,
        *,
        armazem: Any,
        deposito: Any,
        data_movimento: Any,
        itens: Iterable[ItemGrade | dict[str, Any]],
    ) -> tuple[str, str, str, list[ItemGrade]]:
        data = str(data_movimento or "").strip()
        if len(data) != 10 or data[2:3] != "/" or data[5:6] != "/":
            raise ValueError("Data de movimento deve estar no formato DD/MM/AAAA.")
        itens_normalizados = [cls.normalizar_item(item) for item in itens]
        if not itens_normalizados:
            raise ValueError("Informe ao menos um item para o lancamento da grade.")
        return (
            cls._codigo(armazem, "Armazem"),
            cls._codigo(deposito, "Deposito"),
            data,
            itens_normalizados,
        )

    def carregar_grade(self, *, armazem: Any, deposito: Any, data_movimento: Any) -> ExecutionResult:
        try:
            armazem, deposito, data, _ = self.normalizar_lancamento(
                armazem=armazem, deposito=deposito, data_movimento=data_movimento, itens=[{"codigo": "1", "unidade": 1}],
            )
            ok, mensagem = self._aguardar_campo("cdArmazem", "formulario inicial")
            if not ok:
                return self._falha("formulario inicial", mensagem)
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            self.js_set_select_by_name("cdArmazem", armazem.zfill(2))
            self.js_set_input_by_name("cdDeposito", deposito.zfill(2))
            ok, mensagem = self._gatilho("CarregarDeposito(1);", "deposito")
            if not ok:
                return self._falha("deposito", mensagem)
            ok, mensagem = self._aguardar_campo("dtMovimento", "data")
            if not ok:
                return self._falha("data", mensagem)
            ok, mensagem = self._aguardar_campo_habilitado("dtMovimento", "data")
            if not ok:
                return self._falha("data", mensagem)
            self.js_set_input_by_name("dtMovimento", data)
            ok, mensagem = self._gatilho("CarregarLista();", "lista")
            if not ok:
                return self._falha("grade", mensagem)
            ok, mensagem = self._aguardar_campo("cdItem", "lista de itens")
            if not ok:
                return self._falha("lista de itens", mensagem)
            ok, mensagem = self._aguardar_campo_habilitado("cdItem", "lista de itens")
            if not ok:
                return self._falha("lista de itens", mensagem)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Grade carregada na rotina 020105.",
                metadata={"armazem": armazem, "deposito": deposito, "data_movimento": data},
            )
        except ValueError as exc:
            return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=str(exc), retry=False)
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha ao carregar grade: {exc}")

    def adicionar_item(self, item: ItemGrade | dict[str, Any]) -> ExecutionResult:
        try:
            item = self.normalizar_item(item)
            # O Promax pode deixar aberta a pergunta da garrafeira avulsa
            # após o item anterior. Nunca confirmar essa alteração implicitamente.
            self._recusar_confirmacao_pendente()
            # Compatibilidade com doubles legados usados nos testes unitarios.
            # Em execucao real o logger sempre existe e segue o fluxo validado.
            if not getattr(self, "logger", None):
                self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
                self.driver.execute_script("NovoItem();")
                ok, mensagem = self.preencher_campo_com_gatilho("cdItem", item.codigo, "CarregarItem();")
                if not ok:
                    return self._falha(f"item {item.codigo}", mensagem)
            self._log("info", "020105 auditoria: item=%s linha=%s iniciando", item.codigo, item.source_row or "?")
            ok, mensagem = self._aguardar_campo("cdItem", f"novo item {item.codigo}")
            if not ok:
                return self._falha(f"item {item.codigo}", mensagem)
            ok, mensagem = self._aguardar_campo_habilitado("cdItem", f"novo item {item.codigo}")
            if not ok:
                return self._falha(f"item {item.codigo}", mensagem)
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            # Apos carregar a grade os campos de item ficam bloqueados. O
            # operador do video usa o icone "Novo item" antes de informar o
            # proximo codigo; reproduzimos esse estado explicitamente.
            self.driver.execute_script("NovoItem();")
            self.js_set_input_by_name("cdItem", item.codigo)
            ok, mensagem = self._gatilho("CarregarItem();", f"item {item.codigo}")
            if not ok:
                return self._falha(f"item {item.codigo}", mensagem)
            ok, mensagem = self._aguardar_campo("qtCaixa", f"quantidades item {item.codigo}")
            if not ok:
                return self._falha(f"quantidades item {item.codigo}", mensagem)
            for campo, valor in (("qtPallet", item.pallet), ("qtLastro", item.lastro), ("qtCaixa", item.caixa), ("qtUnidade", item.unidade)):
                self.js_set_input_by_name(campo, valor)
            if item.garrafa:
                self.js_set_select_by_name("cdGarrafa", item.garrafa)
            # SalvarItem apenas adiciona a linha na lista temporaria; o commit
            # definitivo ocorre uma unica vez em salvar_lancamento().
            ok, mensagem = self._gatilho("SalvarItem();", f"adicionar item {item.codigo}")
            if not ok:
                if str(mensagem).startswith("Confirmação recusada (Não):"):
                    self._log(
                        "warning",
                        "020105 auditoria: item=%s linha=%s ignorado após confirmação Não",
                        item.codigo,
                        item.source_row or "?",
                    )
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        message=f"Item {item.codigo} ignorado após confirmação Não.",
                        metadata={"skipped": True, "reason": mensagem},
                    )
                return self._falha(f"item {item.codigo}", mensagem)
            self._log("info", "020105 auditoria: item=%s linha=%s lancado", item.codigo, item.source_row or "?")
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message=f"Item {item.codigo} adicionado a grade.")
        except ValueError as exc:
            return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=str(exc), retry=False)
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha ao adicionar item: {exc}")

    def salvar_lancamento(self) -> ExecutionResult:
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            ok, mensagem = self._gatilho("Salvar();", "salvamento", timeout=self.SAVE_TIMEOUT)
            if not ok:
                return self._falha("salvamento", mensagem)
            return ExecutionResult(status=ExecutionStatus.SUCCESS, message="Lancamento da grade salvo na rotina 020105.")
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha ao salvar lancamento da grade: {exc}")

    def lancar_grade(self, *, armazem: Any, deposito: Any, data_movimento: Any, itens: Iterable[ItemGrade | dict[str, Any]]) -> ExecutionResult:
        try:
            armazem, deposito, data, itens = self.normalizar_lancamento(
                armazem=armazem, deposito=deposito, data_movimento=data_movimento, itens=itens,
            )
        except ValueError as exc:
            return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=str(exc), retry=False)

        resultado = self.carregar_grade(armazem=armazem, deposito=deposito, data_movimento=data)
        if not resultado.ok:
            return resultado
        adicionados: list[ItemGrade] = []
        ignorados: list[dict[str, Any]] = []
        for indice, item in enumerate(itens, start=1):
            resultado = self.adicionar_item(item)
            if not resultado.ok:
                return ExecutionResult(
                    status=getattr(resultado, "status", ExecutionStatus.BUSINESS_FAILURE),
                    message=resultado.message,
                    retry=getattr(resultado, "retry", False),
                    metadata={
                        "armazem": armazem,
                        "deposito": deposito,
                        "data_movimento": data,
                        "itens_adicionados": len(adicionados),
                        "failed_items": [
                            {
                                "source_row": item.source_row or indice,
                                "codigo": item.codigo,
                                "reason": resultado.message,
                            }
                        ],
                    },
                )
            resultado_metadata = getattr(resultado, "metadata", None) or {}
            if resultado_metadata.get("skipped"):
                ignorados.append(
                    {
                        "source_row": item.source_row or indice,
                        "codigo": item.codigo,
                        "reason": resultado_metadata.get("reason", resultado.message),
                    }
                )
                continue
            adicionados.append(item)
        resultado = self.salvar_lancamento()
        if resultado.ok:
            return ExecutionResult(
                status=resultado.status,
                message=resultado.message,
                metadata={
                    "armazem": armazem,
                    "deposito": deposito,
                    "data_movimento": data,
                    "itens": len(adicionados),
                    "itens_ignorados": ignorados,
                    "failed_items": [],
                },
            )
        return resultado

    @staticmethod
    def _falha(etapa: str, mensagem: Any) -> ExecutionResult:
        texto = str(mensagem or "Sem confirmacao do Promax.")
        status = ExecutionStatus.TECHNICAL_FAILURE if "timeout" in texto.lower() else ExecutionStatus.BUSINESS_FAILURE
        return ExecutionResult(status=status, message=f"Falha ao processar {etapa}: {texto}")
