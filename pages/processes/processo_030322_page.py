from __future__ import annotations

import datetime as dt
import re
import time
import unicodedata

from selenium.webdriver.common.by import By

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


class Processo030322Page(RotinaPage):
    """
    Page Object da rotina 030322 (PW02136R).

    A rotina trabalha com intervalo de mapa/caixa, data e filtros de status do
    mapa. Ela fica pronta para ser usada pelo fluxo de fechamento de mapas sem
    acoplar aqui a regra de negocio de quando deve ser chamada.
    """

    FRAME_ROTINA = 1

    STATUS_MAPAS = {
        "a": "A",
        "aberto": "A",
        "abertos": "A",
        "f": "F",
        "fechado": "F",
        "fechados": "F",
        "l": "L",
        "liberado": "L",
        "liberados": "L",
        "t": "T",
        "todos": "T",
    }

    @staticmethod
    def normalizar_numero(valor, *, nome: str, obrigatorio: bool = True) -> str:
        if valor is None:
            if obrigatorio:
                raise ValueError(f"{nome} obrigatorio.")
            return ""

        texto = str(valor).strip()
        if not texto:
            if obrigatorio:
                raise ValueError(f"{nome} obrigatorio.")
            return ""

        if re.fullmatch(r"\d+\.0+", texto):
            texto = texto.split(".", 1)[0]

        texto = re.sub(r"\D", "", texto)
        if not texto:
            if obrigatorio:
                raise ValueError(f"{nome} invalido.")
            return ""

        return texto

    @classmethod
    def normalizar_mapa(cls, valor, *, obrigatorio: bool = True) -> str:
        return cls.normalizar_numero(valor, nome="Mapa", obrigatorio=obrigatorio)

    @classmethod
    def normalizar_caixa(cls, valor, *, obrigatorio: bool = True) -> str:
        return cls.normalizar_numero(valor, nome="Caixa", obrigatorio=obrigatorio)

    @staticmethod
    def normalizar_data(valor, *, obrigatorio: bool = False) -> str:
        if valor is None:
            if obrigatorio:
                raise ValueError("Data obrigatoria.")
            return ""

        texto = str(valor).strip()
        if not texto:
            if obrigatorio:
                raise ValueError("Data obrigatoria.")
            return ""

        if texto == "00/00/0000":
            return texto

        if re.fullmatch(r"\d{8}", texto):
            texto = f"{texto[:2]}/{texto[2:4]}/{texto[4:]}"

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
            data = dt.datetime.strptime(texto, "%Y-%m-%d").date()
            return data.strftime("%d/%m/%Y")

        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", texto):
            dt.datetime.strptime(texto, "%d/%m/%Y")
            return texto

        raise ValueError(f"Data invalida: {texto}")

    @classmethod
    def normalizar_status_mapas(cls, valor) -> str:
        texto = str(valor or "todos").strip().lower()
        status = cls.STATUS_MAPAS.get(texto)
        if not status:
            raise ValueError(f"Status de mapas invalido: {valor}")
        return status

    def _entrar_formulario(self, timeout: int = 15):
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)
        self.wait_for_js_condition(
            "return !!(document.forms && document.forms['form1']);",
            timeout=timeout,
            description="formulario da 030322 carregado",
        )

    def _garantir_tela_parametros(self, timeout: int = 15):
        self._entrar_formulario(timeout=timeout)
        tem_campos = self.driver.execute_script(
            """
            return !!(
                document.getElementsByName('mapaInicial')[0]
                && document.getElementsByName('mapaFinal')[0]
                && document.getElementsByName('data')[0]
            );
            """
        )
        if tem_campos:
            return

        self.driver.execute_script(
            """
            if (typeof VoltarRelatorio === 'function') {
                VoltarRelatorio();
                return true;
            }
            var botao = document.getElementsByName('selimp')[0];
            if (botao) {
                botao.click();
                return true;
            }
            if (document.form1) {
                document.form1.opcao.value = '00';
                document.form1.submit();
                return true;
            }
            return false;
            """
        )
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA, timeout=timeout)
        self.wait_for_js_condition(
            """
            return !!(
                document.forms
                && document.forms['form1']
                && document.getElementsByName('mapaInicial')[0]
                && document.getElementsByName('mapaFinal')[0]
                && document.getElementsByName('data')[0]
            );
            """,
            timeout=timeout,
            description="parametros da 030322 carregados",
        )

    def _marcar_checkbox(self, nome: str, marcado: bool):
        self.js_set_checkbox_by_name(nome, bool(marcado), force_click=True)
        if nome == "idMapasAtualizados":
            self.driver.execute_script("if (typeof ControleMapas === 'function') ControleMapas();")

    def _marcar_radio_mapas(self, status: str):
        return self.js_set_radio_by_name("mapas", status)

    def _ler_parametros_formulario(self) -> dict[str, str]:
        return self.driver.execute_script(
            """
            function valor(nome) {
                var campo = document.getElementsByName(nome)[0] || document.getElementById(nome);
                return campo ? String(campo.value || '') : null;
            }
            return {
                mapaInicial: valor('mapaInicial'),
                mapaFinal: valor('mapaFinal'),
                nrCaixaInicial: valor('nrCaixaInicial'),
                nrCaixaFinal: valor('nrCaixaFinal'),
                data: valor('data')
            };
            """
        ) or {}

    def _preencher_data(self, valor: str) -> dict:
        return self.driver.execute_script(
            """
            var valor = String(arguments[0] || '');
            var form = document.forms && document.forms['form1'];
            var campo = (form && form.elements && form.elements['data'])
                || document.getElementsByName('data')[0]
                || document.getElementById('data');
            if (!campo) {
                return {ok: false, error: 'campo data nao encontrado'};
            }
            try { campo.disabled = false; campo.readOnly = false; } catch (e) {}
            try { campo.scrollIntoView(true); } catch (e) {}
            try { campo.focus(); } catch (e) {}
            campo.value = valor;
            try { campo.setAttribute('value', valor); } catch (e) {}
            try {
                if (typeof FormataCampo === 'function') {
                    FormataCampo(campo, '99/99/9999');
                }
            } catch (e) {}
            try {
                if (document.createEvent) {
                    var inputEvent = document.createEvent('HTMLEvents');
                    inputEvent.initEvent('input', true, true);
                    campo.dispatchEvent(inputEvent);
                    var changeEvent = document.createEvent('HTMLEvents');
                    changeEvent.initEvent('change', true, true);
                    campo.dispatchEvent(changeEvent);
                    var blurEvent = document.createEvent('HTMLEvents');
                    blurEvent.initEvent('blur', true, true);
                    campo.dispatchEvent(blurEvent);
                } else if (campo.fireEvent) {
                    campo.fireEvent('onpropertychange');
                    campo.fireEvent('onchange');
                    campo.fireEvent('onblur');
                }
            } catch (e) {}
            try { campo.blur(); } catch (e) {}
            return {
                ok: true,
                value: String(campo.value || ''),
                defaultValue: String(campo.defaultValue || ''),
                name: String(campo.name || '')
            };
            """,
            valor,
        ) or {}

    @staticmethod
    def _normalizar_texto_alerta(texto) -> str:
        texto = str(texto or "").lower()
        texto = unicodedata.normalize("NFKD", texto)
        return "".join(char for char in texto if not unicodedata.combining(char))

    @classmethod
    def _alertas_sem_mapa(cls, alertas) -> list[str]:
        encontrados = []
        for alerta in alertas or []:
            normalizado = cls._normalizar_texto_alerta(alerta)
            if "nao existem mapas" in normalizado or "nao existe mapas" in normalizado:
                encontrados.append(str(alerta))
        return encontrados

    def preencher_parametros(
        self,
        *,
        mapa_inicial=None,
        mapa_final=None,
        caixa_inicial="0",
        caixa_final="999999",
        data=None,
        mapas: str = "todos",
        lista_descartavel: bool = False,
        lista_produtos: bool = False,
        somente_resumo: bool = False,
        mapas_atualizados: bool = False,
    ) -> ExecutionResult:
        try:
            mapa_ini = self.normalizar_mapa(mapa_inicial, obrigatorio=False)
            mapa_fim = self.normalizar_mapa(mapa_final, obrigatorio=False)
            caixa_ini = self.normalizar_caixa(caixa_inicial, obrigatorio=False)
            caixa_fim = self.normalizar_caixa(caixa_final, obrigatorio=False)
            data_fmt = self.normalizar_data(data, obrigatorio=False)
            status_mapas = self.normalizar_status_mapas(mapas)

            if mapa_ini and not mapa_fim:
                mapa_fim = mapa_ini
            if caixa_ini and not caixa_fim:
                caixa_fim = caixa_ini

            self._garantir_tela_parametros()
            payload = {
                "mapaInicial": mapa_ini,
                "mapaFinal": mapa_fim,
                "nrCaixaInicial": caixa_ini,
                "nrCaixaFinal": caixa_fim,
                "data": data_fmt,
            }
            for nome, valor in payload.items():
                if valor:
                    if nome == "data":
                        resultado_data = self._preencher_data(valor)
                        if not resultado_data.get("ok"):
                            raise RuntimeError(resultado_data.get("error") or "falha ao preencher data")
                    else:
                        self.js_set_input_by_name(nome, valor)

            preenchimento = self._ler_parametros_formulario()
            faltantes = [nome for nome, valor in preenchimento.items() if valor is None]
            if faltantes:
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message=f"Campos nao encontrados na 030322: {', '.join(faltantes)}",
                    metadata={"campos_faltantes": faltantes},
                )
            divergentes = {
                nome: {"esperado": esperado, "atual": preenchimento.get(nome, "")}
                for nome, esperado in payload.items()
                if esperado and preenchimento.get(nome, "") != esperado
            }
            if divergentes:
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message="Campos da 030322 nao mantiveram os valores preenchidos.",
                    metadata={"campos_divergentes": divergentes, "preenchimento": preenchimento},
                )

            self._marcar_radio_mapas(status_mapas)
            self._marcar_checkbox("listaDescart", lista_descartavel)
            self._marcar_checkbox("listaProdutos", lista_produtos)
            self._marcar_checkbox("idSomenteResumo", somente_resumo)
            self._marcar_checkbox("idMapasAtualizados", mapas_atualizados)

            alertas = self.lidar_com_alertas(tentativas=1, timeout=1, max_alertas=3)
            self.logger.info(
                "030322 | Parametros preenchidos: mapaInicial=%s | mapaFinal=%s | caixaInicial=%s | caixaFinal=%s | data=%s | mapas=%s | listaProdutos=%s",
                preenchimento.get("mapaInicial"),
                preenchimento.get("mapaFinal"),
                preenchimento.get("nrCaixaInicial"),
                preenchimento.get("nrCaixaFinal"),
                preenchimento.get("data"),
                status_mapas,
                bool(lista_produtos),
            )
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Parametros da 030322 preenchidos.",
                metadata={
                    "parametros": {
                        **payload,
                        "mapas": status_mapas,
                        "lista_descartavel": bool(lista_descartavel),
                        "lista_produtos": bool(lista_produtos),
                        "somente_resumo": bool(somente_resumo),
                        "mapas_atualizados": bool(mapas_atualizados),
                    },
                    "preenchimento": preenchimento,
                    "alertas": alertas,
                },
            )
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao preencher parametros da 030322: {exc}",
            )

    def visualizar(self, **parametros) -> ExecutionResult:
        resultado = self.preencher_parametros(**parametros)
        if not resultado.ok:
            return resultado

        try:
            self._entrar_formulario()
            botao = self.find_element((By.NAME, "BotVisualizar"))
            self.js_click_ie(botao)
            retorno = {"acionado": "BotVisualizar"}
            alertas = self.lidar_com_alertas(tentativas=2, timeout=2, max_alertas=5)
            alertas_sem_mapa = self._alertas_sem_mapa(alertas)
            if alertas_sem_mapa:
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=alertas_sem_mapa[0],
                    retry=False,
                    metadata={
                        **(resultado.metadata or {}),
                        "acao": retorno,
                        "alertas_apos_acao": alertas,
                        "sem_mapa_para_listar": True,
                    },
                )
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Visualizacao da 030322 acionada.",
                metadata={
                    **(resultado.metadata or {}),
                    "acao": retorno,
                    "alertas_apos_acao": alertas,
                },
            )
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao visualizar a 030322: {exc}",
            )

    def configurar_faturamento_automatico(self, **parametros) -> ExecutionResult:
        resultado = self.preencher_parametros(**parametros)
        if not resultado.ok:
            return resultado

        try:
            self._entrar_formulario()
            retorno = self.driver.execute_script(
                """
                window.confirm = function(){ return true; };
                if (typeof msgbxNaoSim === 'function') {
                    msgbxNaoSim = function(titulo, mensagem, sim, nao) {
                        if (typeof sim === 'function') { sim(); }
                        return true;
                    };
                }
                if (typeof ConfigFatAutom === 'function') {
                    ConfigFatAutom();
                    return {acionado: 'ConfigFatAutom'};
                }
                if (document.form1) {
                    document.form1.opcao.value = 2;
                    if (typeof EnviarFormulario === 'function') {
                        EnviarFormulario();
                    } else {
                        document.form1.submit();
                    }
                    return {acionado: 'submit_opcao_2'};
                }
                return {erro: 'form1 nao encontrado'};
                """
            )
            alertas = self.lidar_com_alertas(tentativas=2, timeout=2, max_alertas=5)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message="Configuracao de faturamento automatico da 030322 acionada.",
                metadata={
                    **(resultado.metadata or {}),
                    "acao": retorno,
                    "alertas_apos_acao": alertas,
                },
            )
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao configurar faturamento automatico da 030322: {exc}",
            )

    def extrair_pagina_json(self) -> dict:
        self._entrar_formulario()
        return self.driver.execute_script(
            """
            function valorCampo(nome) {
                var el = document.getElementsByName(nome)[0] || document.getElementById(nome);
                if (!el) return null;
                if (el.type === 'checkbox' || el.type === 'radio') return !!el.checked;
                return el.value || '';
            }
            var radios = [];
            var maps = document.getElementsByName('mapas');
            for (var i = 0; i < maps.length; i++) {
                radios.push({value: maps[i].value, checked: !!maps[i].checked, disabled: !!maps[i].disabled});
            }
            return {
                rotina: '030322',
                campos: {
                    mapaInicial: valorCampo('mapaInicial'),
                    mapaFinal: valorCampo('mapaFinal'),
                    nrCaixaInicial: valorCampo('nrCaixaInicial'),
                    nrCaixaFinal: valorCampo('nrCaixaFinal'),
                    data: valorCampo('data')
                },
                mapas: radios,
                opcoes: {
                    listaDescart: valorCampo('listaDescart'),
                    listaProdutos: valorCampo('listaProdutos'),
                    idSomenteResumo: valorCampo('idSomenteResumo'),
                    idMapasAtualizados: valorCampo('idMapasAtualizados')
                },
                texto: document.body ? document.body.innerText : ''
            };
            """
        )

    def extrair_relatorio_json(self, *, timeout_segundos: int = 10) -> dict:
        """
        Extrai a prestacao de contas gerada pela 030322.

        O Promax renderiza o relatorio em texto monoespacado dentro do pre#rel e
        pode paginar o conteudo. Por isso guardamos o texto bruto e tambem uma
        versao estruturada das linhas principais para consumo do painel.
        """
        paginas = self._coletar_paginas_relatorio(timeout_segundos=timeout_segundos)
        texto_completo = "\n".join(item.get("texto") or "" for item in paginas)
        return self._parse_relatorio_texto(texto_completo, paginas=paginas)

    def _coletar_paginas_relatorio(self, *, timeout_segundos: int = 10) -> list[dict]:
        primeira = self._ler_pagina_relatorio(timeout_segundos=timeout_segundos)
        paginas = [primeira]
        total_paginas = int(primeira.get("total_paginas") or 1)
        for pagina in range(2, total_paginas + 1):
            self._ir_para_pagina_relatorio(pagina)
            paginas.append(self._ler_pagina_relatorio(timeout_segundos=timeout_segundos, pagina_esperada=pagina))
        return paginas

    def _ler_pagina_relatorio(self, *, timeout_segundos: int = 10, pagina_esperada: int | None = None) -> dict:
        limite = time.time() + max(1, timeout_segundos)
        ultimo = {}
        while time.time() < limite:
            try:
                dados = self.driver.execute_script(
                    """
                    var rel = document.getElementById('rel') || document.getElementsByName('rel')[0];
                    var texto = rel ? (rel.innerText || rel.textContent || '') : '';
                    var mPag = texto.match(/Pag\\.\\s*(\\d+)/i);
                    var mTotal = texto.match(/p[áa]ginas?\\s+de\\s+1\\s+at[eé]\\s+(\\d+)/i);
                    var irpara = document.getElementsByName('irpara')[0];
                    var paginaatual = document.getElementsByName('paginaatual')[0];
                    return {
                        texto: texto,
                        pagina: mPag ? Number(mPag[1]) : (paginaatual && paginaatual.value ? Number(paginaatual.value) : null),
                        total_paginas: mTotal ? Number(mTotal[1]) : null,
                        irpara_max: irpara && irpara.outerHTML ? irpara.outerHTML : ''
                    };
                    """
                ) or {}
                texto = str(dados.get("texto") or "")
                if texto.strip() and (pagina_esperada is None or int(dados.get("pagina") or pagina_esperada) == pagina_esperada):
                    if not dados.get("total_paginas"):
                        total = self._inferir_total_paginas(texto, dados.get("irpara_max"))
                        dados["total_paginas"] = total
                    ultimo = dados
                    break
                ultimo = dados
            except Exception:
                pass
            time.sleep(0.4)
        if not str(ultimo.get("texto") or "").strip():
            raise RuntimeError("Relatorio 030322 nao carregou texto para extracao.")
        return ultimo

    def _ir_para_pagina_relatorio(self, pagina: int) -> None:
        self.driver.execute_script(
            """
            var ir = document.getElementsByName('irpara')[0];
            var atual = document.getElementsByName('paginaatual')[0];
            var opcao = document.getElementsByName('opcao')[0];
            var opcaorelat = document.getElementsByName('opcaorelat')[0];
            if (ir) ir.value = String(arguments[0]);
            if (atual) atual.value = String(arguments[0]);
            if (opcao) opcao.value = 88;
            if (opcaorelat) opcaorelat.value = 0;
            if (typeof IrParaPagina === 'function') {
                IrParaPagina();
                return true;
            }
            if (document.form1) {
                document.form1.submit();
                return true;
            }
            return false;
            """,
            int(pagina),
        )

    @staticmethod
    def _inferir_total_paginas(texto: str, html_irpara: str | None = None) -> int:
        candidatos = [int(item) for item in re.findall(r"Pag\.\s*(\d+)", texto or "", flags=re.I)]
        html = str(html_irpara or "")
        candidatos.extend(int(item) for item in re.findall(r"Informar p.ginas de 1 at.\s*(\d+)", html, flags=re.I))
        return max(candidatos or [1])

    @classmethod
    def _parse_relatorio_texto(cls, texto: str, *, paginas: list[dict] | None = None) -> dict:
        linhas = [cls._limpar_linha_relatorio(line) for line in str(texto or "").splitlines()]
        cabecalho = cls._parse_cabecalho(linhas)
        notas, totais_notas = cls._parse_notas(linhas)
        vasilhames, totais_vasilhame = cls._parse_vasilhames(linhas)
        resumo_financeiro = cls._parse_resumo_financeiro(linhas)
        devolucoes = [item for item in notas if str(item.get("situacao") or "").upper() == "DEV" or item.get("valor_devolucao")]
        return {
            "rotina": "030322",
            "cabecalho": cabecalho,
            "notas": notas,
            "vasilhames": vasilhames,
            "resumo_financeiro": resumo_financeiro,
            "totais_notas": totais_notas,
            "totais_vasilhame": totais_vasilhame,
            "resumo": {
                "notas": len(notas),
                "devolucoes": len(devolucoes),
                "valor_notas": totais_notas.get("valor_nota") or cls._somar_money(notas, "valor_nota"),
                "valor_devolucao": totais_notas.get("valor_devolucao") or cls._somar_money(notas, "valor_devolucao"),
                "valor_liquido": totais_notas.get("valor_liquido") or cls._somar_money(notas, "valor_liquido"),
                "vasilhames": len(vasilhames),
            },
            "paginas": [
                {"pagina": item.get("pagina"), "total_paginas": item.get("total_paginas")}
                for item in (paginas or [])
            ],
            "texto": texto,
        }

    @staticmethod
    def _limpar_linha_relatorio(linha: str) -> str:
        return re.sub(r"</?b>", "", str(linha or "")).rstrip()

    @staticmethod
    def _parse_money(valor: str | None):
        texto = str(valor or "").strip()
        if not texto:
            return None
        negativo = texto.endswith("-")
        texto = texto.rstrip("-").replace(".", "").replace(",", ".")
        try:
            numero = float(texto)
        except ValueError:
            return None
        return -numero if negativo else numero

    @classmethod
    def _somar_money(cls, rows: list[dict], key: str) -> float:
        return round(sum(float(item.get(key) or 0) for item in rows), 2)

    @staticmethod
    def _parse_cabecalho(linhas: list[str]) -> dict:
        texto = "\n".join(linhas[:12])
        dados = {}
        patterns = {
            "mapa": r"Mapa:\s*([\d.]+)",
            "data_mapa": r"Mapa:\s*[\d.]+\s+de\s+(\d{2}/\d{2}/\d{4})",
            "status": r"Prestacao de Contas\s+([A-Z]+)",
            "revenda": r"Rev\.\:\s*(\d+)",
            "veiculo": r"Veiculo\s*\.\.:\s*([^\n]+?)\s+Transp\.",
            "motorista": r"Motorista\s*\.+:\s*([^\n]+?)\s+Ajudante 1",
            "ajudante1": r"Ajudante 1\s*\.+:\s*([^\n]+)",
            "ajudante2": r"Ajudante 2\s*\.+:\s*([^\n]+)",
            "caixa": r"Caixa\s*\.+:\s*([^\n]+?)\s+Carga Atual",
            "conferente": r"Conferente\s*\.+:\s*([^\n]+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, texto, flags=re.I)
            if match:
                dados[key] = match.group(1).strip()
        if "mapa" in dados:
            dados["mapa"] = dados["mapa"].replace(".", "")
        return dados

    @classmethod
    def _parse_notas(cls, linhas: list[str]) -> tuple[list[dict], dict]:
        notas = []
        totais = {}
        in_section = False
        ultima = None
        for linha in linhas:
            if "UNB/Codigo" in linha and "Valor Liquido" in linha:
                in_section = True
                continue
            if in_section and ("VASILHAME" in linha or "RESUMO FINANCEIRO" in linha):
                break
            if not in_section:
                continue
            if "Totais" in linha:
                valores = re.findall(r"\d[\d.]*,\d{2}-?", linha)
                if len(valores) >= 3:
                    totais = {
                        "qtd": int(re.search(r"Totais\s*\.*:\s*(\d+)", linha).group(1)) if re.search(r"Totais\s*\.*:\s*(\d+)", linha) else None,
                        "valor_nota": cls._parse_money(valores[-3]),
                        "valor_devolucao": cls._parse_money(valores[-2]),
                        "valor_liquido": cls._parse_money(valores[-1]),
                    }
                continue
            nota_match = re.match(
                r"^\s*(\d+)\s+(.+?)\s+(\d{3}\.\d{3})\s+(\d{3})(?:\s+(DEV))?\s+(\d+)\s+(.+?)\s+(\d[\d.]*,\d{2})(?:\s+(\d[\d.]*,\d{2}-?))?(?:\s+(\d[\d.]*,\d{2}-?))?\s*$",
                linha,
            )
            if nota_match:
                valor_devolucao = nota_match.group(9) if nota_match.group(5) == "DEV" else None
                valor_liquido = nota_match.group(10) or (None if valor_devolucao else nota_match.group(9))
                ultima = {
                    "nb": nota_match.group(1).strip(),
                    "cliente": nota_match.group(2).strip(),
                    "nota": nota_match.group(3).replace(".", ""),
                    "serie": nota_match.group(4),
                    "situacao": nota_match.group(5) or "",
                    "operacao": nota_match.group(6),
                    "condicao_pagamento": nota_match.group(7).strip(),
                    "valor_nota": cls._parse_money(nota_match.group(8)),
                    "valor_devolucao": cls._parse_money(valor_devolucao),
                    "valor_liquido": cls._parse_money(valor_liquido),
                    "linhas_complementares": [],
                }
                notas.append(ultima)
                continue
            complemento = re.match(r"^\s{45,}(DEV)?\s*(\d+)\s+(.+?)\s+(\d[\d.]*,\d{2})(?:\s+(\d[\d.]*,\d{2}-?))?", linha)
            if complemento and ultima:
                ultima["linhas_complementares"].append({
                    "situacao": complemento.group(1) or "",
                    "operacao": complemento.group(2),
                    "condicao_pagamento": complemento.group(3).strip(),
                    "valor_nota": cls._parse_money(complemento.group(4)),
                    "valor_devolucao": cls._parse_money(complemento.group(5)),
                })
        return notas, totais

    @classmethod
    def _parse_vasilhames(cls, linhas: list[str]) -> tuple[list[dict], dict]:
        rows = []
        totais = {}
        in_section = False
        for linha in linhas:
            if linha.strip() == "VASILHAME":
                in_section = True
                continue
            if in_section and "RESUMO FINANCEIRO" in linha:
                break
            if not in_section:
                continue
            if "Totais" in linha:
                valores = re.findall(r"\d[\d.]*,\d{2}-?", linha)
                if valores:
                    totais["saida"] = cls._parse_money(valores[0])
                    if len(valores) > 1:
                        totais["retorno"] = cls._parse_money(valores[1])
                    if len(valores) > 2:
                        totais["diferenca"] = cls._parse_money(valores[-1])
                continue
            match = re.match(r"^\s*(\d+)\s+(\S+)\s+(.+?)\s+(\d[\d.]*,\d{2})\s+(.+)$", linha)
            if not match:
                continue
            restante = match.group(5)
            qtdes = re.findall(r"\d[\d.]*/\d{2}-?|/\d{2}", restante)
            valores = re.findall(r"\d[\d.]*,\d{2}-?", restante)
            rows.append({
                "codigo": match.group(1),
                "unidade": match.group(2),
                "denominacao": match.group(3).strip(),
                "preco": cls._parse_money(match.group(4)),
                "saida_qtd": qtdes[0] if len(qtdes) > 0 else "",
                "saida_valor": cls._parse_money(valores[0]) if len(valores) > 0 else None,
                "retorno_qtd": qtdes[1] if len(qtdes) > 1 else "",
                "retorno_valor": cls._parse_money(valores[1]) if len(valores) > 1 else None,
                "diferenca_qtd": qtdes[2] if len(qtdes) > 2 else "",
                "diferenca_valor": cls._parse_money(valores[2]) if len(valores) > 2 else None,
            })
        return rows, totais

    @classmethod
    def _parse_resumo_financeiro(cls, linhas: list[str]) -> dict:
        start = next((idx for idx, linha in enumerate(linhas) if "RESUMO FINANCEIRO" in linha), -1)
        if start < 0:
            return {}
        return {"linhas": [linha.strip() for linha in linhas[start + 1:] if linha.strip()]}
