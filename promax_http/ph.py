"""Download por HTTP das telas PH (modelo novo do Promax, jQuery/AJAX).

Essas rotinas (ex.: 01.05.07.04.02 = PH050094) nao tem frameset nem form1. A
pagina e uma casca com o formPadrao; o resto e AJAX, definido em
../scripts/jqfuncoes.js e no PH0500xx.js de cada tela:

- execAjaxHtml: posta o formPadrao com ajaxJson=N e devolve o HTML do
  formulario da tela (aqui so serve para conferir que a tela abriu);
- execAjaxJson: posta formPadrao (ajaxJson=S, ppopcao=0, opcao da acao,
  callRetorno da tela) + campos do formulario + parametros extras e devolve JSON.
  Para "Gerar CSV" o JSON traz downloadCSV[0].dsCaminhoArquivoCSV, que a pagina
  abre numa janela (abreJanelaDownload): esse caminho e o proprio arquivo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from promax_http import alertas as classificar
from promax_http.cliente import ClientePromax, Rotina
from promax_http.erros import ExportacaoNaoEntendida, PromaxHttpErro, RelatorioSemConteudo

_UNIDADE_RE = re.compile(r'\$\("#unidadeMenu"\)\.val\("(\d+)"\)')

# Chaves de erro que o verificaErroExecucao() do jqfuncoes.js mostra em alert.
_CHAVES_ERRO = ("dsErroPP00100", "dsErroAbertura", "erro8000Mensagem")


@dataclass(frozen=True)
class PedidoCsvPh:
    """O que a funcao GerarCSV da tela manda: a opcao, o callRetorno da tela e os
    campos (formulario serializado + parametros extras, na ordem do navegador)."""

    opcao: str
    call_retorno: str
    campos: tuple[tuple[str, str], ...]


def carregar_tela(cliente: ClientePromax, rotina: Rotina, marca: str) -> str:
    """execAjaxHtml(null, "conteudo"): confere que a tela entregou o formulario."""
    resposta = cliente.http.post(
        cliente.base, {**rotina.form.campos, "opcao": "1", "ajaxJson": "N"}
    )
    if marca not in resposta.texto:
        raise PromaxHttpErro(
            f"Tela PH {rotina.programa} nao trouxe o formulario ({marca}). Envie a pasta de rastro."
        )
    return resposta.texto


def unidade_ativa(rotina: Rotina) -> str | None:
    """A casca da tela PH preenche $("#unidadeMenu").val("<codigo>") no ready()."""
    achado = _UNIDADE_RE.search(rotina.html_rotina)
    return achado.group(1) if achado else None


def trocar_unidade(cliente: ClientePromax, rotina: Rotina, unidade: str) -> Rotina:
    """Troca a unidade da tela PH e so devolve a tela se ela confirmar a unidade.

    A unidade fica presa ao SessionID: o trocaEmpresa() da casca (ppopcao=14) mantem
    o SessionID e o CSV continua saindo da unidade antiga (visto em 18/11: "Sume"
    baixou Patos). Por isso a troca usa o mesmo pedido do combo de unidade das
    rotinas comuns (ppopcao=7 + changeUNB), que devolve a casca com SessionID novo.
    Sem a casca confirmar a unidade, para com erro: nunca gera na unidade errada.
    """
    unidade = str(unidade).strip()
    if unidade_ativa(rotina) == unidade:
        _log(cliente, "Unidade %s ja ativa na tela %s.", unidade, rotina.programa)
        return rotina
    _log(cliente, "Trocando a unidade da tela %s para %s ...", rotina.programa, unidade)
    nova = cliente.reabrir_em_unidade(rotina, unidade)
    if unidade_ativa(nova) != unidade:
        raise PromaxHttpErro(
            f"Troca de unidade na tela {rotina.programa} nao pegou: pedi {unidade}, "
            f"a tela esta em {unidade_ativa(nova)}. Envie a pasta de rastro."
        )
    _log(cliente, "Unidade %s confirmada na tela %s.", unidade, rotina.programa)
    return nova


def gerar_csv(cliente: ClientePromax, rotina: Rotina, pedido: PedidoCsvPh, destino: Path) -> Path:
    _log(cliente, "Gerando o CSV na tela %s (o Promax pode demorar) ...", rotina.programa)
    padrao = {
        **rotina.form.campos,
        "opcao": pedido.opcao,
        "ppopcao": "0",
        "ajaxJson": "S",
        "callRetorno": pedido.call_retorno,
    }
    resposta = cliente.http.post(cliente.base, [*padrao.items(), *pedido.campos])
    caminho = caminho_do_csv(resposta.texto)
    arquivo = cliente.baixar_arquivo(urljoin(cliente.base, caminho), destino)
    if arquivo is None:
        raise ExportacaoNaoEntendida(f"O Promax gerou {caminho}, mas o download nao trouxe um CSV.")
    return arquivo


def caminho_do_csv(texto: str) -> str:
    """Le o JSON do Gerar CSV e devolve dsCaminhoArquivoCSV, ou levanta o erro certo."""
    dados = _ler_json(texto)
    for chave in _CHAVES_ERRO:
        for item in dados.get(chave) or []:
            raise ExportacaoNaoEntendida(f"Promax recusou a geracao: {item.get('dsErro', item)}")
    caminhos = [item.get("dsCaminhoArquivoCSV", "") for item in dados.get("downloadCSV") or []]
    caminho = next((c.strip() for c in caminhos if c and c.strip()), "")
    mensagens = [item.get("mensagem", "") for item in dados.get("mensagemRetorno") or []]
    if caminho:
        return caminho
    vazio = classificar.contem(mensagens, classificar.SEM_CONTEUDO)
    if vazio:
        raise RelatorioSemConteudo(vazio)
    raise ExportacaoNaoEntendida(f"Gerar CSV nao devolveu arquivo. Mensagens: {mensagens or texto[:300]!r}")


def _ler_json(texto: str) -> dict:
    try:
        dados = json.loads(texto)
    except ValueError:
        # O COBOL as vezes manda espacos/caracteres soltos; tenta o primeiro objeto.
        achado = re.search(r"\{.*\}", texto, re.DOTALL)
        if not achado:
            raise ExportacaoNaoEntendida(f"Resposta do Gerar CSV nao e JSON: {texto[:300]!r}")
        try:
            dados = json.loads(achado.group(0), strict=False)
        except ValueError as exc:
            raise ExportacaoNaoEntendida(f"Resposta do Gerar CSV nao e JSON: {texto[:300]!r}") from exc
    return dados if isinstance(dados, dict) else {}


def _log(cliente: ClientePromax, msg: str, *args) -> None:
    if cliente.logger:
        cliente.logger.info(msg, *args)
