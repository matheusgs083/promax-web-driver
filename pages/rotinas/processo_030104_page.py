import os
import csv
import pandas as pd
import datetime as dt
import time
from core.execution_result import ExecutionResult, ExecutionStatus
from pages.rotina_page import RotinaPage


class Processo030104Page(RotinaPage):
    FRAME_ROTINA = 1

    # --- MÃ‰TODO DE LEITURA (ESTÃTICO/OFFLINE) ---
    def ler_planilha_pedidos(self, caminho_planilha):
        """LÃª o Excel e agrupa itens por pedido (CabeÃ§alho) com tratamento de tipos."""
        self.logger.info(f"Iniciando leitura da planilha: {caminho_planilha}")

        try:
            df = pd.read_excel(caminho_planilha, dtype=str)
            df.columns = [str(c).strip().lower() for c in df.columns]

            colunas_cabecalho = ["mapa", "vendedor", "operacao", "cliente"]

            if not set(colunas_cabecalho).issubset(df.columns):
                raise ValueError(f"Colunas obrigatÃ³rias ausentes: {colunas_cabecalho}")

            df[colunas_cabecalho] = df[colunas_cabecalho].ffill()
            df = df.dropna(subset=["item"])

            pedidos_agrupados = []

            for chaves, grupo in df.groupby(colunas_cabecalho, dropna=False):
                itens = []
                for _, row in grupo.iterrows():
                    ttv_raw = str(row.get("ttv", "")).strip()
                    ttv_val = ttv_raw.replace(".", ",") if ttv_raw and ttv_raw != "nan" else None

                    itens.append({
                        "codigo": str(row["item"]).strip().split(".")[0],
                        "qtd": str(row["quantidade"]).strip().split(".")[0],
                        "ttv": ttv_val,
                    })

                pedidos_agrupados.append({
                    "mapa": str(chaves[0]).split(".")[0] if chaves[0] not in ["0", None] else "0",
                    "vendedor": str(chaves[1]).split(".")[0],
                    "operacao": str(chaves[2]).split(".")[0],
                    "cliente": str(chaves[3]).split(".")[0],
                    "itens": itens,
                })

            self.logger.info(f"Sucesso: {len(pedidos_agrupados)} pedidos agrupados.")
            return pedidos_agrupados

        except Exception as e:
            self.logger.error(f"Erro ao processar planilha: {str(e)}")
            return []

    # --- MÃ‰TODOS DE AUTOMAÃ‡ÃƒO ---
    def digitar_pedido_completo(self, dados_pedido, caminho_log_csv):
        """Executa a inserÃ§Ã£o completa de um pedido no sistema."""
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)

        self.driver.execute_script("window.msgbxSimNao = function(t, m, fSim, fNao){ fSim(); };")

        mapa = str(dados_pedido["mapa"]).strip()
        cliente = str(dados_pedido["cliente"]).strip()

        try:
            ok_mapa, msg_mapa = self.preencher_campo_com_gatilho("nrMapa", mapa, "CarregaMapa(2);")
            if not ok_mapa:
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"Mapa {mapa} invÃ¡lido ou nÃ£o carregado: {msg_mapa}",
                )

            self._fechar_aba_mpd_se_aberta()

            campos_head = [
                ("cdVendedor", dados_pedido["vendedor"], "CarregaVendedor();"),
                ("cdOperacao", dados_pedido["operacao"], "CarregaOperacao();"),
                ("cdDestinatario", cliente, "CarregaCliente();"),
            ]

            for campo, val, trigger in campos_head:
                ok, msg = self.preencher_campo_com_gatilho(campo, val, trigger)
                if not ok:
                    self.executar_gatilho_e_aguardar("Cancelar();")
                    return ExecutionResult(
                        status=ExecutionStatus.BUSINESS_FAILURE,
                        message=f"Erro no cabeÃ§alho ({campo}): {msg}",
                    )

            sucessos = 0
            total_itens = len(dados_pedido["itens"])
            colunas_log = ["data_hora", "mapa", "cliente", "produto", "quantidade", "status", "motivo"]

            for item in dados_pedido["itens"]:
                ok_item, motivo = self._processar_item(item)

                self.registrar_log_csv(caminho_log_csv, colunas_log, {
                    "data_hora": dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    "mapa": mapa,
                    "cliente": cliente,
                    "produto": item["codigo"],
                    "quantidade": item["qtd"],
                    "status": "SUCESSO" if ok_item else "FALHA",
                    "motivo": motivo,
                })

                if ok_item:
                    sucessos += 1

            if sucessos == 0:
                self.executar_gatilho_e_aguardar("Cancelar();")
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message="Pedido abortado: nenhum item foi aceito pelo sistema.",
                )

            salvou, msg_final = self.executar_gatilho_e_aguardar("Salvar();")
            if not salvou:
                status = (
                    ExecutionStatus.TECHNICAL_FAILURE
                    if "timeout" in str(msg_final).lower()
                    else ExecutionStatus.BUSINESS_FAILURE
                )
                return ExecutionResult(status=status, message=msg_final)

            if sucessos < total_itens:
                return ExecutionResult(
                    status=ExecutionStatus.PARTIAL_SUCCESS,
                    message=f"Pedido salvo com sucesso parcial: {sucessos}/{total_itens} item(ns) aceitos. {msg_final}",
                )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=msg_final,
            )
        except Exception as e:
            self.logger.exception(f"Falha tÃ©cnica ao digitar pedido do mapa {mapa}: {e}")
            try:
                self.executar_gatilho_e_aguardar("Cancelar();")
            except Exception as cancel_error:
                self.logger.debug(f"Falha ao cancelar pedido apÃ³s erro tÃ©cnico do mapa {mapa}: {cancel_error}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=str(e),
            )

    def _processar_item(self, item):
        """LÃ³gica de baixo nÃ­vel para preencher a grade de produtos."""
        try:
            self.driver.execute_script("NovoItem();")

            self.js_set_input_by_name("codProduto", item["codigo"])
            self.js_set_input_by_name("qtPedida", item["qtd"])

            if item.get("ttv"):
                self.js_set_input_by_name("valorTTV", item["ttv"])

            res, msg = self.executar_gatilho_e_aguardar("document.getElementById('IMGadicionar').click();")

            if not res:
                self.driver.execute_script("LimpaDetalhe();")

            return res, msg

        except Exception as e:
            self.logger.warning(f"Erro ao processar item {item['codigo']}: {e}")
            self.driver.execute_script("try { LimpaDetalhe(); } catch(e) {}")
            return False, str(e)

    def _fechar_aba_mpd_se_aberta(self):
        """
        Tratamento para o modal de 'Motivo de NÃ£o Carga' que aparece
        quando um cliente possui restriÃ§Ãµes de logÃ­stica.
        """
        script_mpd = """
            var div = document.getElementById('DivMsg');
            if (div && (div.style.display !== 'none' && div.style.visibility !== 'hidden')) {
                var mot = document.getElementsByName('cdMotivoNaoCarga')[0];
                if(mot) mot.value = '99';
                var btn = document.getElementsByName('BotConfirmMPD')[0];
                if(btn) { btn.click(); return true; }
            }
            return false;
        """
        try:
            if self.driver.execute_script(script_mpd):
                self.wait_for_js_condition(
                    "var div = document.getElementById('DivMsg'); return !div || div.style.display === 'none' || div.style.visibility === 'hidden';",
                    timeout=3,
                    description="fechamento do modal MPD",
                )
                self.logger.info("Modal MPD detectado e fechado automaticamente.")
        except Exception as e:
            self.logger.warning(f"Falha ao tratar modal MPD automaticamente: {e}")
