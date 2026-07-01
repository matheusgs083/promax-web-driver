import os
import time

from selenium.common.exceptions import TimeoutException

from core.config.settings import get_settings
from core.services.report_download_service import capturar_download_relatorio
from pages.common.rotina_page import RotinaPage


class Relatorio03114902Page(RotinaPage):
    """
    Rotina 03.11.49.02 - Relatorio PCD.

    Modelo novo Ajax (PH050158). Segue o mesmo estilo da 0105070402:
    aplica filtros via JS e aciona o botao de geracao via JS.
    """

    JS_APLICAR_FILTROS = r"""
    try {
        var filtros = arguments[0] || {};

        function norm(value) {
            return ((value || '') + '').replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '').toUpperCase();
        }
        function fire(el) {
            try { el.dispatchEvent(new Event('input', {bubbles: true})); } catch(e) {}
            try { el.dispatchEvent(new Event('change', {bubbles: true})); } catch(e) {}
            try { jQuery(el).trigger('input').trigger('change').trigger('blur'); } catch(e) {}
        }
        function byId(id) {
            return document.getElementById(id);
        }
        function setSelect(id, wanted) {
            var sel = byId(id);
            if (!sel) return false;
            var alvo = norm(wanted);
            for (var i = 0; i < sel.options.length; i++) {
                var opt = sel.options[i];
                var txt = norm(opt.text);
                if (norm(opt.value) === alvo || txt === alvo || txt.indexOf(alvo) !== -1) {
                    sel.selectedIndex = i;
                    fire(sel);
                    return true;
                }
            }
            return false;
        }
        function setCheckbox(id, checked) {
            var el = byId(id);
            if (!el) return false;
            el.checked = !!checked;
            fire(el);
            return true;
        }
        function setRadio(id, checked) {
            var el = byId(id);
            if (!el) return false;
            el.checked = !!checked;
            fire(el);
            return true;
        }
        function setText(id, value) {
            if (value === null || value === undefined) return false;
            var el = byId(id);
            if (!el) return false;
            el.value = value;
            fire(el);
            return true;
        }

        var status = {};
        status.classificacao = setSelect('opClassificacao', filtros.classificacao);
        status.csvQlikview = setCheckbox('checkQlik', filtros.csv_qlikview);
        status.rota = setCheckbox('checkRota', filtros.tipo_mapa_rota);
        status.as = setCheckbox('checkAs', filtros.tipo_mapa_as);
        status.todasOperacoes = setCheckbox('checkTodasOper', filtros.todas_operacoes);
        status.mapasRoteirizados = setRadio('idRoteirizadoA', !!filtros.mapas_roteirizados);
        status.todosMapas = setRadio('idRoteirizadoB', !filtros.mapas_roteirizados);
        status.mapaInicial = setText('mapaInicial', filtros.mapa_inicial);
        status.mapaFinal = setText('mapaFinal', filtros.mapa_final);
        status.dataInicial = setText('dataInicial', filtros.data_inicial);
        status.dataFinal = setText('dataFinal', filtros.data_final);
        status.roadshowInicial = setText('roadInicial', filtros.roadshow_inicial);
        status.roadshowFinal = setText('roadFinal', filtros.roadshow_final);
        status.transportadoraInicial = setText('cdTransportadoraInicial', filtros.transportadora_inicial);
        status.transportadoraFinal = setText('cdTransportadoraFinal', filtros.transportadora_final);
        status.armazem = setSelect('opArmazem', filtros.armazem);
        var hiddenArmazem = byId('hiddenopArmazem');
        if (hiddenArmazem) hiddenArmazem.value = filtros.armazem;

        return {ok: true, status: status};
    } catch (e) {
        return {ok: false, error: (e && e.message) ? e.message : String(e)};
    }
    """

    JS_CLICK_CSV = r"""
    try {
        var csvGeo = arguments[0];
        function norm(value) {
            return ((value || '') + '').replace(/\s+/g, ' ').replace(/^\s+|\s+$/g, '').toUpperCase();
        }
        function coletar(tagName, destino) {
            var itens = document.getElementsByTagName(tagName);
            for (var j = 0; j < itens.length; j++) {
                destino[destino.length] = itens[j];
            }
        }
        var elementos = [];
        coletar('input', elementos);
        coletar('button', elementos);
        coletar('a', elementos);
        for (var i = 0; i < elementos.length; i++) {
            var el = elementos[i];
            var txt = norm((el.value || '') + ' ' + (el.innerText || '') + ' ' + (el.title || '') + ' ' + (el.name || '') + ' ' + (el.id || ''));
            if (txt.indexOf('CSV') === -1) continue;
            if (csvGeo && txt.indexOf('GEO') === -1) continue;
            if (!csvGeo && txt.indexOf('GEO') !== -1) continue;
            if (el.disabled) continue;
            (function(btn) {
                window.setTimeout(function() {
                    if (btn.click) btn.click();
                    else if (btn.fireEvent) btn.fireEvent('onclick');
                }, 0);
            })(el);
            return {ok: true, target: txt};
        }
        return {ok: false, error: 'botao CSV nao encontrado'};
    } catch (e) {
        return {ok: false, error: (e && e.message) ? e.message : String(e)};
    }
    """

    def gerar_relatorio(
        self,
        unidade=None,
        classificacao="Mapa",
        csv_qlikview=False,
        tipo_mapa_rota=True,
        tipo_mapa_as=True,
        todas_operacoes=False,
        mapas_roteirizados=True,
        mapa_inicial="0",
        mapa_final="999999",
        data_inicial=None,
        data_final=None,
        roadshow_inicial="0",
        roadshow_final="99",
        transportadora_inicial="0",
        transportadora_final="999999",
        armazem="Todos",
        csv_geo=False,
        timeout=60,
        nome_arquivo="03114902.csv",
    ):
        if isinstance(unidade, list):
            resultados = []
            for item in unidade:
                base, ext = os.path.splitext(nome_arquivo)
                nome_por_unidade = f"{base}_{item}{ext or '.csv'}"
                resultados.append(
                    self.gerar_relatorio(
                        unidade=item,
                        classificacao=classificacao,
                        csv_qlikview=csv_qlikview,
                        tipo_mapa_rota=tipo_mapa_rota,
                        tipo_mapa_as=tipo_mapa_as,
                        todas_operacoes=todas_operacoes,
                        mapas_roteirizados=mapas_roteirizados,
                        mapa_inicial=mapa_inicial,
                        mapa_final=mapa_final,
                        data_inicial=data_inicial,
                        data_final=data_final,
                        roadshow_inicial=roadshow_inicial,
                        roadshow_final=roadshow_final,
                        transportadora_inicial=transportadora_inicial,
                        transportadora_final=transportadora_final,
                        armazem=armazem,
                        csv_geo=csv_geo,
                        timeout=timeout,
                        nome_arquivo=nome_por_unidade,
                    )
                )
            if all(resultado is True or (isinstance(resultado, tuple) and resultado[0]) for resultado in resultados):
                return True, f"{len(resultados)} execucao(oes) concluida(s)"
            return False, f"Falha em uma ou mais execucoes: {resultados}"

        self.switch_to_default_content()
        self._aguardar_modelo_novo(timeout=timeout)

        if unidade:
            self._trocar_unidade_modelo_novo(unidade, timeout=timeout)

        self._aplicar_filtros(
            classificacao=classificacao,
            csv_qlikview=csv_qlikview,
            tipo_mapa_rota=tipo_mapa_rota,
            tipo_mapa_as=tipo_mapa_as,
            todas_operacoes=todas_operacoes,
            mapas_roteirizados=mapas_roteirizados,
            mapa_inicial=mapa_inicial,
            mapa_final=mapa_final,
            data_inicial=data_inicial,
            data_final=data_final,
            roadshow_inicial=roadshow_inicial,
            roadshow_final=roadshow_final,
            transportadora_inicial=transportadora_inicial,
            transportadora_final=transportadora_final,
            armazem=armazem,
        )
        self._clicar_botao_gerar(csv_geo=csv_geo)

        diretorio_base = get_settings().download_dir
        subpasta = getattr(self, "subpasta_download", None)
        diretorio = diretorio_base / subpasta if subpasta else diretorio_base
        return capturar_download_relatorio(
            nome_arquivo_final=nome_arquivo,
            diretorio_destino=str(diretorio),
        )

    def _aguardar_modelo_novo(self, timeout):
        self.wait_for_js_condition(
            "return !!document.getElementById('opClassificacao') && !!document.getElementById('botGerarCSV');",
            timeout=min(timeout, 20),
            description="formulario 03114902 carregado",
        )
        try:
            self.wait_for_js_condition(
                "return !window.jQuery || jQuery.active === 0;",
                timeout=3,
                description="ajax inicial da rotina concluido",
            )
        except TimeoutException:
            self.logger.debug("Ajax da 03114902 ainda ativo; seguindo porque o formulario ja esta disponivel.")

    def _trocar_unidade_modelo_novo(self, unidade, timeout):
        unidade = str(unidade).strip()
        resultado = self.driver.execute_script(
            """
            try {
                if (document.getElementById('unidadeMenu')) {
                    document.getElementById('unidadeMenu').value = arguments[0];
                }
                if (typeof trocaEmpresa === 'function') {
                    trocaEmpresa(arguments[0]);
                    return {ok: true, method: 'trocaEmpresa'};
                }
                return {ok: false, error: 'trocaEmpresa indisponivel'};
            } catch (e) {
                return {ok: false, error: (e && e.message) ? e.message : String(e)};
            }
            """,
            unidade,
        )
        if not resultado or not resultado.get("ok"):
            raise RuntimeError(f"Falha ao trocar unidade na 03114902: {resultado}")

        self.wait_for_js_condition(
            "return !window.jQuery || jQuery.active === 0;",
            timeout=timeout,
            description=f"troca de unidade {unidade} concluida",
        )
        time.sleep(1)

    def _aplicar_filtros(self, **filtros):
        self.logger.info("Aplicando filtros 03114902 via JS...")
        resultado = self.driver.execute_script(self.JS_APLICAR_FILTROS, filtros)
        if resultado and not resultado.get("ok"):
            raise RuntimeError(f"Falha no JS de filtros 03114902: {resultado}")
        self.logger.info("Filtros 03114902 preenchidos: %s", resultado)
        self.aguardar_loader_oculto(timeout=5)

    def _clicar_botao_gerar(self, csv_geo):
        alvo = "CSV GEO" if csv_geo else "CSV"
        self.logger.info("Clicando no botao %s da rotina 03114902...", alvo)
        resultado = self.driver.execute_script(self.JS_CLICK_CSV, bool(csv_geo))
        if not resultado or not resultado.get("ok"):
            raise RuntimeError(f"Falha ao clicar no botao {alvo}: {resultado}")
        self.logger.info("Botao %s acionado: %s", alvo, resultado.get("target"))
