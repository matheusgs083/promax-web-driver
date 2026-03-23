from dataclasses import dataclass
from enum import Enum
from typing import Any


class ExecutionStatus(str, Enum):
    SUCCESS = "SUCESSO"
    PARTIAL_SUCCESS = "SUCESSO_PARCIAL"
    BUSINESS_FAILURE = "FALHA_NEGOCIO"
    TECHNICAL_FAILURE = "FALHA_TECNICA"
    ABORTED = "ABORTADO"

    @property
    def is_success(self) -> bool:
        return self is ExecutionStatus.SUCCESS

    @property
    def should_retry(self) -> bool:
        return self in {
            ExecutionStatus.PARTIAL_SUCCESS,
            ExecutionStatus.BUSINESS_FAILURE,
            ExecutionStatus.TECHNICAL_FAILURE,
            ExecutionStatus.ABORTED,
        }


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    message: str

    @property
    def ok(self) -> bool:
        return self.status.is_success

    @property
    def should_retry(self) -> bool:
        return self.status.should_retry


def normalize_execution_result(
    result: Any,
    *,
    success_message: str = "Execucao concluida com sucesso",
    failure_message: str = "Execucao retornou falha sem detalhe",
) -> ExecutionResult:
    if isinstance(result, ExecutionResult):
        return result

    if isinstance(result, tuple) and len(result) >= 2:
        ok, message = result[0], str(result[1])
        status = ExecutionStatus.SUCCESS if bool(ok) else ExecutionStatus.BUSINESS_FAILURE
        return ExecutionResult(status=status, message=message)

    if result is True or result is None:
        return ExecutionResult(status=ExecutionStatus.SUCCESS, message=success_message)

    if result is False:
        return ExecutionResult(status=ExecutionStatus.BUSINESS_FAILURE, message=failure_message)

    return ExecutionResult(status=ExecutionStatus.SUCCESS, message=str(result))
