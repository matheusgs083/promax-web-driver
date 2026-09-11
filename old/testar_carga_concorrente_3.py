from __future__ import annotations

import json
import time
import traceback
from datetime import datetime
from pathlib import Path

import pages.common.rotina_page as rotina_page_module
from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger
from pages.reports.relatorio_020502_page import Relatorio020502Page
from pages.reports.relatorio_030237_page import Relatorio030237Page
from pages.reports.relatorio_120616_page import Relatorio120616Page
from testar_geracao_concorrente import (
    _executar_concorrente,
    _preparar_especificacao,
)


logger = get_logger("TESTE_CARGA_CONCORRENTE_3")
settings = get_settings()
CONCORRENCIA = 3

ALVOS = {
    "030237": "3610007",
    "120616": "3610008",
    "020502": "2210004",
}


def _salvar_relatorio(relatorio: dict) -> Path:
    pasta = Path(LOGS_DIR) / "diagnosticos_concorrencia"
    pasta.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta / f"carga_concorrente_3_{timestamp}.json"
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return caminho


def main() -> int:
    driver = None
    especificacoes = []
    paginas = []
    original_capturador = rotina_page_module.capturar_download_por_formulario
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_saida = Path(settings.download_dir) / "teste_concorrencia_3" / timestamp
    relatorio = {
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "concorrencia": CONCORRENCIA,
        "alvos": ALVOS,
        "historico_referencia": {
            "030237": {"media_s": 188.8, "p90_s": 328, "max_s": 507},
            "120616": {"media_s": 33.2, "taxa_sucesso": "54.5%"},
            "020502": {"media_s": 49.0, "p90_s": 47, "max_s": 227},
        },
        "preparacao": [],
        "execucao": {},
        "janelas_apos_carga": [],
        "erros": [],
    }

    def capturar_sem_executar(
        driver_recebido,
        botao,
        nome_arquivo_final,
        diretorio_intermediario=None,
        extensao_final=".csv",
    ):
        nome = nome_arquivo_final.rsplit(".", 1)[0]
        especificacao = _preparar_especificacao(
            driver_recebido,
            botao,
            nome,
            extensao_final,
        )
        especificacoes.append(especificacao)
        relatorio["preparacao"].append(
            {
                "nome": nome,
                "action": especificacao["action_segura"],
                "session_fingerprint": especificacao["session_fingerprint"],
                "metodo": especificacao["metodo"],
                "bytes_formulario": len(especificacao["dados"]),
            }
        )
        return True, "Requisição preparada para carga concorrente 3"

    try:
        driver, menu = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )
        handle_menu = driver.current_window_handle
        rotina_page_module.capturar_download_por_formulario = capturar_sem_executar
        hoje = datetime.now().strftime("%d/%m/%Y")

        janela_030237 = menu.acessar_rotina("030237")
        page_030237 = Relatorio030237Page(
            janela_030237.driver,
            janela_030237.handle_menu,
        )
        paginas.append(("030237", driver.current_window_handle, page_030237))
        page_030237.gerar_relatorio(
            unidade=ALVOS["030237"],
            quebra1="14",
            itens="s",
            data_inicial=hoje,
            data_final=hoje,
            nome_arquivo="030237_carga3.csv",
        )

        driver.switch_to.window(handle_menu)
        driver.switch_to.default_content()
        janela_120616 = menu.acessar_rotina("120616")
        page_120616 = Relatorio120616Page(
            janela_120616.driver,
            janela_120616.handle_menu,
        )
        paginas.append(("120616", driver.current_window_handle, page_120616))
        page_120616.gerar_relatorio(
            unidade=ALVOS["120616"],
            opcao_rel="3",
            mes_ano=datetime.now().strftime("%m/%Y"),
            nome_arquivo="120616_carga3.csv",
        )

        driver.switch_to.window(handle_menu)
        driver.switch_to.default_content()
        janela_020502 = menu.acessar_rotina("020502")
        page_020502 = Relatorio020502Page(
            janela_020502.driver,
            janela_020502.handle_menu,
        )
        paginas.append(("020502", driver.current_window_handle, page_020502))
        page_020502.gerar_relatorio(
            unidade=ALVOS["020502"],
            opcao_rel="1",
            listar_produtos=True,
            listar_vasilhames_garrafeiras=False,
            tipo_data="E",
            periodo_inicial=hoje,
            periodo_final=hoje,
            nome_arquivo="020502_carga3.csv",
        )

        if len(especificacoes) != 3:
            raise RuntimeError(
                f"Esperadas 3 requisições preparadas; obtidas {len(especificacoes)}"
            )

        resultados, tempo_parede = _executar_concorrente(
            especificacoes,
            pasta_saida,
            max_workers=CONCORRENCIA,
        )
        soma_tempos = round(sum(item["duracao_segundos"] for item in resultados), 3)
        relatorio["execucao"] = {
            "tempo_parede_segundos": tempo_parede,
            "soma_tempos_individuais": soma_tempos,
            "speedup_por_sobreposicao": round(soma_tempos / tempo_parede, 3)
            if tempo_parede
            else None,
            "todos_ok": all(item["ok"] for item in resultados),
            "resultados": resultados,
        }

        for rotina, handle, pagina in paginas:
            try:
                driver.switch_to.window(handle)
                unidade = pagina.obter_unidade_atual(timeout=2)
                relatorio["janelas_apos_carga"].append(
                    {
                        "rotina": rotina,
                        "ativa": True,
                        "unidade": str(unidade),
                        "unidade_esperada": ALVOS[rotina],
                        "unidade_preservada": str(unidade) == ALVOS[rotina],
                    }
                )
            except Exception as exc:
                relatorio["janelas_apos_carga"].append(
                    {
                        "rotina": rotina,
                        "ativa": False,
                        "erro": f"{type(exc).__name__}: {exc}",
                    }
                )
    except Exception as exc:
        relatorio["erros"].append(
            {
                "tipo": type(exc).__name__,
                "mensagem": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        logger.exception("Teste de carga concorrente 3 falhou: %s", exc)
    finally:
        rotina_page_module.capturar_download_por_formulario = original_capturador
        relatorio["fim"] = datetime.now().isoformat(timespec="seconds")
        caminho_relatorio = _salvar_relatorio(relatorio)
        encerrar_driver(driver)

    print(f"RELATORIO_CARGA_3={caminho_relatorio}")
    print(json.dumps(relatorio.get("execucao", {}), ensure_ascii=False, indent=2))
    return 0 if not relatorio["erros"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
