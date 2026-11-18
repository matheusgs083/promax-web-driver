"""Prova de conceito: baixa o CSV de uma rotina do Promax sem abrir o Edge.

Exemplo (120616, unidade Patos, classificacao Gerente, mes atual):

    python -m promax_http.poc --rotina 120616 --unidade 2210003 ^
        --campo opcaoRel=3 --campo mesAno=11/2026

Credenciais e URL vem do .env (PROMAX_URL, PROMAX_USER, PROMAX_PASS), igual
ao resto do projeto. Cada requisicao fica gravada em
logs/promax_http/<data_hora>/ (senha mascarada) para diagnostico.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.observability.logger import get_logger
from promax_http.cliente import ClientePromax
from promax_http.erros import PromaxHttpErro, RelatorioSemConteudo
from promax_http.transporte import Transporte


def _ler_campos(pares: list[str]) -> dict[str, str]:
    campos = {}
    for par in pares:
        nome, sep, valor = par.partition("=")
        if not sep:
            raise SystemExit(f"--campo precisa ser nome=valor (recebi {par!r})")
        campos[nome.strip()] = valor
    return campos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rotina", required=True, help="Codigo digitado no atalho do menu, ex.: 120616")
    parser.add_argument("--unidade", action="append", default=[], help="Codigo ou nome; repita para varias")
    parser.add_argument("--campo", action="append", default=[], help="Campo do formulario, nome=valor")
    parser.add_argument("--menu-id", help="MenuID exato, se o codigo nao for encontrado sozinho")
    parser.add_argument("--saida", type=Path, help="Pasta de saida (padrao: DOWNLOAD_DIR/promax_http)")
    parser.add_argument("--so-abrir", action="store_true", help="So faz login, abre a rotina e lista os campos")
    args = parser.parse_args(argv)

    logger = get_logger("PROMAX_HTTP_POC")
    settings = get_settings()
    if not (settings.promax_url and settings.promax_user and settings.promax_pass):
        logger.error("Configure PROMAX_URL, PROMAX_USER e PROMAX_PASS no .env")
        return 2

    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    rastro = Path(LOGS_DIR) / "promax_http" / f"{carimbo}_{args.rotina}"
    saida = args.saida or Path(settings.download_dir) / "promax_http"
    campos = _ler_campos(args.campo)
    cliente = ClientePromax(settings.promax_url, transporte=Transporte(pasta_rastro=rastro), logger=logger)
    unidades = args.unidade or [None]
    falhas = 0
    inicio = time.time()

    try:
        cliente.login(settings.promax_user, settings.promax_pass, unidade=unidades[0])
        rotina = cliente.abrir_rotina(args.rotina, menu_id=args.menu_id)
        logger.info("Rotina %s aberta: programa %s, MenuID %s", args.rotina, rotina.programa, rotina.menu_id)

        if args.so_abrir:
            print(f"Programa: {rotina.programa}  MenuID: {rotina.menu_id}  Unidade ativa: {rotina.unidade_ativa}")
            print("Unidades:", ", ".join(f"{o.valor} ({o.texto})" for o in rotina.unidades))
            print("Campos do formulario:")
            for nome, valor in rotina.form.campos.items():
                opcoes = rotina.form.opcoes.get(nome)
                extra = f"  opcoes: {[(o.valor, o.texto) for o in opcoes]}" if opcoes else ""
                print(f"  {nome} = {valor!r}{extra}")
            print("Botoes:", ", ".join(rotina.form.botoes))
            return 0

        for unidade in unidades:
            t0 = time.time()
            try:
                if unidade:
                    rotina = cliente.trocar_unidade(rotina, unidade)
                ativa = rotina.unidade_ativa or "unidade"
                destino = saida / f"{args.rotina}_{ativa}_{carimbo}.csv"
                arquivo = cliente.exportar_csv(rotina, campos, destino)
                logger.info("OK %s em %.1fs: %s (%d bytes)", ativa, time.time() - t0, arquivo, arquivo.stat().st_size)
            except RelatorioSemConteudo as exc:
                logger.warning("Unidade %s sem conteudo: %s", unidade, exc)
            except PromaxHttpErro as exc:
                falhas += 1
                logger.error("Unidade %s falhou: %s", unidade, exc)
        cliente.fechar_rotina(rotina)
    except PromaxHttpErro as exc:
        logger.error("Falha: %s", exc)
        falhas += 1
    except Exception:  # PoC: registra tudo e devolve codigo de erro, sem derrubar o console
        logger.exception("Erro inesperado na PoC")
        falhas += 1
    finally:
        try:
            cliente.logoff()
        except Exception as exc:  # o logoff e cortesia; nao muda o resultado
            logger.debug("Logoff falhou: %s", exc)
        logger.info("Tempo total: %.1fs. Rastro em %s", time.time() - inicio, rastro)

    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
