from __future__ import annotations

import json
import re
from collections import OrderedDict
from decimal import Decimal, InvalidOperation
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.observability.logger import get_logger
from promax_http import html
from promax_http.cliente import ClientePromax
from promax_http.pedido_030104 import Digitacao, Parada, catalogo, formatar_ttv, gravar_catalogo, item_lista
from promax_http.transporte import Transporte


logger = get_logger("DIGITACAO_030104")
_ORDER_RE = re.compile(r"Pedido\s+(\d+)\s+gerado", re.IGNORECASE)


def _preco_informado(value: Any) -> str:
    """Normaliza um preço digitado no painel para o formato usado pela 03.01.04."""
    raw = str(value or "").strip().replace("R$", "").replace(" ", "")
    if not raw:
        return ""
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        price = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError("Preço do item inválido.") from exc
    if price <= 0:
        raise ValueError("Preço do item deve ser maior que zero.")
    return formatar_ttv(f"{price:.2f}".replace(".", ","))


def _load(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Arquivo de digitação inválido: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("pedidos"), list) or not payload["pedidos"]:
        raise ValueError("O arquivo deve conter unidade e pelo menos um pedido.")
    if len(payload["pedidos"]) > 100:
        raise ValueError("Máximo de 100 pedidos por job.")
    for index, order in enumerate(payload["pedidos"], start=1):
        if not isinstance(order, dict) or not str(order.get("vendedor") or "").strip() or not str(order.get("cliente") or "").strip():
            raise ValueError(f"Pedido {index}: vendedor e cliente são obrigatórios.")
        items = order.get("itens")
        if not isinstance(items, list) or not items or len(items) > 200:
            raise ValueError(f"Pedido {index}: informe de 1 a 200 itens.")
        products = [str(item.get("produto") or "").strip() for item in items if isinstance(item, dict)]
        if len(products) != len(items) or any(not product.isdigit() for product in products) or len(set(products)) != len(products):
            raise ValueError(f"Pedido {index}: produto inválido ou repetido.")
        if any(not isinstance(item.get("quantidade"), int) or item["quantidade"] < 1 for item in items):
            raise ValueError(f"Pedido {index}: quantidade deve ser inteira e maior que zero.")
        for item in items:
            _preco_informado(item.get("preco"))
    return payload


def _groups(orders: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for order in orders:
        key = str(order.get("mapa") or "NOVO1").strip() or "NOVO1"
        grouped.setdefault(key, []).append(order)
    return list(grouped.items())


def _prepare_order(digitacao: Digitacao, order: dict[str, Any], conditions: set[str]) -> dict[str, Any]:
    digitacao.enviar("11", "Vendedor", {"cdVendedor": str(order["vendedor"])})
    digitacao.enviar("4", "Operação", {"cdOperacao": "1"})
    digitacao.informar_cliente(str(order["cliente"]))
    explicitly_requested = str(order.get("cond_pagto") or "").strip().zfill(3) if str(order.get("cond_pagto") or "").strip() else ""
    standard = str(digitacao.form.get("cdCondicaoPagto") or "").strip()
    if not standard:
        options = [value for value, _label in digitacao.opcoes_novas.get("cdCondicaoPagto", []) if value]
        if len(options) == 1:
            standard = options[0]
            digitacao.form["cdCondicaoPagto"] = standard
        elif not explicitly_requested:
            raise Parada("Condição padrão do cliente não foi retornada pelo Promax.")
    requested = explicitly_requested or standard
    if not requested:
        raise Parada("Selecione uma condição de pagamento; o Promax não devolveu a condição padrão deste cliente.")
    if requested not in conditions:
        raise Parada(f"Condição {requested} não está liberada na unidade.")
    if digitacao.condicao_travada and (not standard or requested != standard):
        raise Parada(f"Condição travada pelo Promax; padrão do cliente é {standard}.")
    digitacao.form["cdCondicaoPagto"] = requested
    digitacao.enviar("8", "Liberar itens")
    accepted: list[dict[str, Any]] = []
    for source in order["itens"]:
        product = str(source["produto"])
        qty = str(source["quantidade"])
        requested_price = _preco_informado(source.get("preco"))
        digitacao.form.update({"codProduto": product, "qtPedida": qty, "valorTTV": requested_price, "idUnidade": "N", "vlAliquota": "", "vlFCI": "", "itensLista": "".join(item_lista(item) for item in accepted), "carregando": "1"})
        response = digitacao.enviar("7", "Adicionar item")
        if "AdicionaLista" not in response:
            raise Parada(f"Produto {product} não foi aceito pelo Promax.")
        accepted.append({"cdProduto": product, "qtPedida": qty, "vlTtv": requested_price or formatar_ttv(str(digitacao.form.get("valorTTV") or "")), "sgUnidade": str(digitacao.form.get("siglaUnidade") or ""), "idUnidade": "N", "cdOpcaoSub": "0"})
    return {"condicao_padrao_cliente": standard, "condicao_usada": requested, "condicao_travada": digitacao.condicao_travada, "accepted": accepted}


def main(arquivo: str | None = None, unidade: str | None = None, salvar: bool = True, job_id: str = "") -> ExecutionResult:
    if not arquivo:
        raise ValueError("--arquivo é obrigatório.")
    payload = _load(arquivo)
    unit = str(unidade or payload.get("unidade") or "").strip()
    if not unit:
        raise ValueError("Unidade é obrigatória.")
    settings = get_settings()
    trace = Path(LOGS_DIR) / "promax_http" / f"{datetime.now():%Y%m%d_%H%M%S}_digitacao_030104"
    client = ClientePromax(settings.promax_url, transporte=Transporte(pasta_rastro=trace), logger=logger)
    routine = None
    results: list[dict[str, Any]] = []
    maps: dict[str, str] = {}
    catalogue: dict[str, Any] = {"unidade": unit, "condicoes": []}
    try:
        client.login(settings.promax_user, settings.promax_pass, unidade=unit)
        routine = client.abrir_rotina("030104")
        catalogue = catalogo(routine)
        gravar_catalogo(catalogue)
        conditions = {str(item.get("codigo") or "") for item in catalogue.get("condicoes") or []}
        for map_key, orders in _groups(payload["pedidos"]):
            digitacao = Digitacao(client, routine, logger)
            number = map_key if map_key.isdigit() else "0"
            digitacao.enviar("2", "Mapa", {"nrMapa": number})
            map_number = str(digitacao.form.get("nrMapa") or "").strip()
            if not map_number:
                raise Parada(f"Mapa {map_key}: Promax não devolveu o número do mapa.")
            maps[map_key] = map_number
            for order in orders:
                result: dict[str, Any] = {"ref": str(order.get("ref") or ""), "status": "nao_digitado", "pedido": "", "mapa": map_number, "motivo": "", "motivo_digitacao": str(order.get("motivo_digitacao") or "")}
                try:
                    header = _prepare_order(digitacao, order, conditions)
                    result.update({key: header[key] for key in ("condicao_padrao_cliente", "condicao_usada", "condicao_travada")})
                    result["itens"] = [{"produto": item["cdProduto"], "quantidade": int(item["qtPedida"]), "unidade": item["sgUnidade"], "preco": item["vlTtv"]} for item in header["accepted"]]
                    if salvar:
                        text = digitacao.enviar("6", "Salvar", {"itensLista": "".join(item_lista(item) for item in header["accepted"]), "idEnviaRoad": "S", "carregando": "0"}, parar_em_alerta=False)
                        found = _ORDER_RE.search(text)
                        if not found:
                            raise Parada("Promax não confirmou a geração do pedido.")
                        result.update(status="salvo", pedido=found.group(1))
                        print(json.dumps({"event": "promax_partial_result", "job_id": job_id, "ref": result["ref"], "pedido": result["pedido"], "mapa": map_number, "status": "salvo"}, ensure_ascii=True), flush=True)
                    else:
                        result["status"] = "validado"
                except Exception as exc:
                    result.update(status="recusado", motivo=str(exc))
                results.append(result)
        saved = sum(item["status"] == "salvo" for item in results)
        failed = len(results) - saved if salvar else sum(item["status"] != "validado" for item in results)
        status = ExecutionStatus.SUCCESS if not failed else ExecutionStatus.PARTIAL_SUCCESS if saved else ExecutionStatus.BUSINESS_FAILURE
        return ExecutionResult(status=status, message=f"03.01.04: {saved} pedido(s) salvo(s), {failed} recusado(s).", retry=False, metadata={"mapas": maps, "pedidos": results, "catalogo": catalogue})
    except Exception as exc:
        return ExecutionResult(status=ExecutionStatus.TECHNICAL_FAILURE, message=f"Falha na 03.01.04: {exc}", retry=False, metadata={"mapas": maps, "pedidos": results, "catalogo": catalogue})
    finally:
        try:
            if routine is not None:
                client.fechar_rotina(routine)
            client.logoff()
        except Exception:
            pass
