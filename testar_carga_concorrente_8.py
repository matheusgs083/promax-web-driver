from __future__ import annotations

import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import pages.common.rotina_page as rotina_page_module
from core.config.project_paths import LOGS_DIR
from core.config.settings import get_settings
from core.execution.entrypoint_helpers import encerrar_driver, iniciar_sessao_padrao
from core.observability.logger import get_logger
from pages.reports.relatorio_020220_page import Relatorio020220Page
from pages.reports.relatorio_020502_page import Relatorio020502Page
from pages.reports.relatorio_030237_page import Relatorio030237Page
from pages.reports.relatorio_0512_page import Relatorio0512Page
from pages.reports.relatorio_120616_page import Relatorio120616Page
from pages.reports.relatorio_120601_page import Relatorio120601Page
from pages.reports.relatorio_140506_page import Relatorio140506Page
from pages.reports.relatorio_150501_page import Relatorio150501Page
from testar_geracao_concorrente import (
    _executar_concorrente,
    _preparar_especificacao,
)


logger = get_logger("TESTE_CARGA_CONCORRENTE_8")
settings = get_settings()
CONCORRENCIA = 8

ALVOS = {
    "030237": "3610007",
    "120616": "3610008",
    "020502": "2210004",
    "020220": "3610006",
    "150501": "3610008",
    "0512": "0640001",
    "120601": "0640002",
    "140506": "2210003",
}


def _salvar_relatorio(relatorio: dict) -> Path:
    pasta = Path(LOGS_DIR) / "diagnosticos_concorrencia"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"carga_concorrente_8_{datetime.now():%Y%m%d_%H%M%S}.json"
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
    pasta_saida = Path(settings.download_dir) / "teste_concorrencia_8" / timestamp
    relatorio = {
        "inicio": datetime.now().isoformat(timespec="seconds"),
        "concorrencia": CONCORRENCIA,
        "alvos": ALVOS,
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
        return True, "Requisição preparada para carga concorrente 8"

    def abrir(menu, handle_menu, codigo, classe):
        driver.switch_to.window(handle_menu)
        driver.switch_to.default_content()
        janela = menu.acessar_rotina(codigo)
        pagina = classe(janela.driver, janela.handle_menu)
        paginas.append((codigo, driver.current_window_handle, pagina))
        return pagina

    try:
        driver, menu = iniciar_sessao_padrao(
            logger,
            settings,
            settings.unidade_relatorios,
        )
        handle_menu = driver.current_window_handle
        rotina_page_module.capturar_download_por_formulario = capturar_sem_executar
        hoje = datetime.now().strftime("%d/%m/%Y")
        mes_ano = datetime.now().strftime("%m/%Y")
        primeiro_dia_mes_atual = datetime.now().replace(day=1)
        primeiro_dia_mes_anterior = (
            primeiro_dia_mes_atual - timedelta(days=1)
        ).replace(day=1)

        page_030237 = abrir(
            menu,
            handle_menu,
            "030237",
            Relatorio030237Page,
        )
        page_030237.gerar_relatorio(
            unidade=ALVOS["030237"],
            quebra1="14",
            itens="s",
            data_inicial=hoje,
            data_final=hoje,
            nome_arquivo="030237_carga8.csv",
        )

        page_120616 = abrir(
            menu,
            handle_menu,
            "120616",
            Relatorio120616Page,
        )
        page_120616.gerar_relatorio(
            unidade=ALVOS["120616"],
            opcao_rel="3",
            mes_ano=mes_ano,
            nome_arquivo="120616_carga8.csv",
        )

        page_020502 = abrir(
            menu,
            handle_menu,
            "020502",
            Relatorio020502Page,
        )
        page_020502.gerar_relatorio(
            unidade=ALVOS["020502"],
            opcao_rel="1",
            listar_produtos=True,
            listar_vasilhames_garrafeiras=False,
            tipo_data="E",
            periodo_inicial=hoje,
            periodo_final=hoje,
            nome_arquivo="020502_carga8.csv",
        )

        page_020220 = abrir(
            menu,
            handle_menu,
            "020220",
            Relatorio020220Page,
        )
        page_020220.gerar_relatorio(
            unidade=ALVOS["020220"],
            opcao_rel="01",
            mercadoria_todos=False,
            mercadoria_garrafeira=True,
            mercadoria_vasilhame=True,
            selecao_comodatos="T",
            nome_arquivo="020220_carga8.csv",
        )

        page_150501 = abrir(
            menu,
            handle_menu,
            "150501",
            Relatorio150501Page,
        )
        page_150501.gerar_relatorio(
            unidade=ALVOS["150501"],
            visao="02",
            periodo="M",
            mes_ano=mes_ano,
            totaliza_periodo=True,
            nome_arquivo="150501_carga8.csv",
        )

        page_0512 = abrir(
            menu,
            handle_menu,
            "0512",
            Relatorio0512Page,
        )
        page_0512.gerar_relatorio(
            unidade=ALVOS["0512"],
            opcao_rel="11",
            ano=datetime.now().strftime("%Y"),
            id_converte_hecto=True,
            nome_arquivo="0512_carga8.csv",
        )

        page_120601 = abrir(
            menu,
            handle_menu,
            "120601",
            Relatorio120601Page,
        )
        page_120601.gerar_relatorio(
            unidade=ALVOS["120601"],
            opcao_rel="01",
            ini_vencimento=f"01/{datetime.now():%m/%Y}",
            fim_vencimento=hoje,
            ini_especie=4,
            fim_especie=4,
            id_notas_tit_nao_atu=False,
            nome_arquivo="120601_carga8.csv",
        )

        page_140506 = abrir(
            menu,
            handle_menu,
            "140506",
            Relatorio140506Page,
        )
        page_140506.gerar_relatorio(
            unidade=ALVOS["140506"],
            opcao_rel="01",
            tipo_data="C",
            iniDat=primeiro_dia_mes_anterior.strftime("%d/%m/%Y"),
            fimDat=primeiro_dia_mes_atual.strftime("%d/%m/%Y"),
            nome_arquivo="140506_carga8.csv",
        )

        if len(especificacoes) != CONCORRENCIA:
            raise RuntimeError(
                f"Esperadas {CONCORRENCIA} requisições; obtidas {len(especificacoes)}"
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
            "segundos_economizados": round(soma_tempos - tempo_parede, 3),
            "economia_percentual": round(
                (soma_tempos - tempo_parede) / soma_tempos,
                4,
            )
            if soma_tempos
            else 0,
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
        logger.exception("Teste de carga concorrente 8 falhou: %s", exc)
    finally:
        rotina_page_module.capturar_download_por_formulario = original_capturador
        relatorio["fim"] = datetime.now().isoformat(timespec="seconds")
        caminho_relatorio = _salvar_relatorio(relatorio)
        encerrar_driver(driver)

    print(f"RELATORIO_CARGA_8={caminho_relatorio}")
    print(json.dumps(relatorio.get("execucao", {}), ensure_ascii=False, indent=2))
    return 0 if not relatorio["erros"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
