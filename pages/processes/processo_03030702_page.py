import time
import unicodedata
from datetime import datetime
from selenium.common.exceptions import NoAlertPresentException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


class Processo03030702Page(RotinaPage):
    """
    Page Object para a rotina 03030702 (Fechamento/Conferência de Mapa - PW02108C).
    Utiliza leitor multi-estratégia (TR/TD + Regex do innerText + resumoFinanceiro) no iFrameSaida
    e motor duplo no iFrameRetorno para garantir a digitação e liberação do mapa.
    """

    FRAME_ROTINA = 1

    # Mapeamento dinâmico de Descrições de Contas de Saída -> Código de Conta no Promax
    MAPA_DE_CONTAS = [
        # Categorias confirmadas na rotina 03.03.07.02
        ("BLOQUETO BANCARIO", "2"),
        ("BLOQUETO", "2"),

        ("CREDITO EM CONTA", "18"),
        ("CREDITO CONTA", "18"),

        ("TRANSFERENCIA", "43"),

        ("TROCA", "44"),

        # IMPORTANTE: CHEQUE A VISTA deve ficar antes de A VISTA,
        # pois "A VISTA" também aparece dentro de "CHEQUE A VISTA".
        ("CHEQUE A VISTA", "1"),
        ("A VISTA", "27"),
        ("DINHEIRO", "27"),

        ("BONIFICACAO / VERBA", "5"),
        ("BONIFICACAO", "5"),

        # Vasilhame normalmente já vem criado automaticamente pelo Promax.
        ("VASILHAME", "0"),

        ("PGD", "74"),
        ("PIX", "78"),
        ("CHEQUE PRE", "3"),
        ("RECIBO", "75"),
    ]

    CONTAS_SAIDA_IGNORADAS = {
        "SIMPLES REMESSA",
    }

    @staticmethod
    def _valor_conta_para_float(valor):
        texto = str(valor or "").strip()
        if not texto or texto in {"-", "--"}:
            return 0.0

        texto = (
            texto.replace("R$", "")
            .replace("\u00a0", " ")
            .replace(" ", "")
            .strip()
        )
        if not texto:
            return 0.0

        negativo = texto.endswith("-") or texto.startswith("-")
        texto = texto.strip("-")
        if not texto:
            return 0.0

        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        try:
            numero = float(texto)
        except ValueError:
            return None

        if negativo:
            numero = -numero
        return numero

    @classmethod
    def _diferenca_tem_valor(cls, valor):
        numero = cls._valor_conta_para_float(valor)
        if numero is None:
            return True
        return abs(numero) > 0.00001

    @classmethod
    def _valores_conta_equivalentes(cls, esperado, encontrado):
        valor_esperado = cls._valor_conta_para_float(esperado)
        valor_encontrado = cls._valor_conta_para_float(encontrado)
        if valor_esperado is None or valor_encontrado is None:
            return str(esperado or "").strip() == str(encontrado or "").strip()
        return abs(valor_esperado - valor_encontrado) <= 0.009

    @staticmethod
    def _normalizar_descricao_conta(valor):
        texto = str(valor or "").strip().upper()
        reparos_mojibake = {
            "\u00c3\u0081": "A",
            "\u00c3\u0080": "A",
            "\u00c3\u0083": "A",
            "\u00c3\u0082": "A",
            "\u00c3\u0089": "E",
            "\u00c3\u008a": "E",
            "\u00c3\u008d": "I",
            "\u00c3\u0093": "O",
            "\u00c3\u0094": "O",
            "\u00c3\u0095": "O",
            "\u00c3\u009a": "U",
            "\u00c3\u0087": "C",
            "\u00c3\u2030": "E",
            "\u00c3\u0160": "E",
            "\u00c3\u2021": "C",
            "\u00c3\u20ac": "A",
            "\u00c3\u0192": "A",
            "\u00c3\u201a": "A",
            "\u00c3\u201c": "O",
            "\u00c3\u201d": "O",
            "\u00c3\u2022": "O",
            "\u00c3\u0161": "U",
        }
        for origem, destino in reparos_mojibake.items():
            texto = texto.replace(origem, destino)

        if "\u00c3" in texto or "\u00c2" in texto:
            try:
                texto = texto.encode("latin1").decode("utf-8")
            except UnicodeError:
                pass

        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
        return " ".join(texto.split())

    JS_RECURSIVE_FRAME_FINDER = """
        function buscarDocumentoPorElemento(testFn) {
            var visitados = [];
            function visto(w) {
                for (var i = 0; i < visitados.length; i++) {
                    if (visitados[i] === w) return true;
                }
                return false;
            }

            function visitar(win) {
                if (!win || visto(win)) return null;
                visitados.push(win);

                var doc = null;
                try { doc = win.document; } catch(e) {}

                if (doc) {
                    try {
                        if (testFn(win, doc)) {
                            return { win: win, doc: doc };
                        }
                    } catch(e) {}
                }

                try {
                    if (win.frames && win.frames.length > 0) {
                        for (var f = 0; f < win.frames.length; f++) {
                            var ret = visitar(win.frames[f]);
                            if (ret) return ret;
                        }
                    }
                } catch(e) {}
                return null;
            }

            var r1 = visitar(window);
            if (r1) return r1;
            try { if (window.parent && window.parent !== window) { var r2 = visitar(window.parent); if (r2) return r2; } } catch(e) {}
            try { if (window.top && window.top !== window && window.top !== window.parent) { var r3 = visitar(window.top); if (r3) return r3; } } catch(e) {}
            return null;
        }

        function getRotinaWin() {
            var ctx = buscarDocumentoPorElemento(function(w, d) {
                return !!(d.getElementsByName('numeroMapa')[0] || d.getElementsByName('BotSalvar')[0] || typeof w.CarregarMapa === 'function');
            });
            return ctx ? ctx.win : window;
        }

        function extrairItensSaidaDoDocumento(doc) {
            var itens = [];
            if (!doc) return itens;

            // Estratégia 1: Varredura de linhas TR e células TD
            try {
                var trs = doc.getElementsByTagName('TR');
                if (!trs || trs.length === 0) trs = doc.getElementsByTagName('tr');
                if (!trs || trs.length === 0) trs = doc.all ? doc.all.tags('TR') : [];

                for (var i = 0; i < trs.length; i++) {
                    var row = trs[i];
                    var tds = row.getElementsByTagName('TD');
                    if (!tds || tds.length === 0) tds = row.getElementsByTagName('td');
                    if (!tds || tds.length === 0) tds = row.cells;

                    if (tds && tds.length >= 3) {
                        var dText = (tds[0].innerText || tds[0].textContent || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
                        var qText = (tds[1].innerText || tds[1].textContent || '').replace(/\\u00a0/g, ' ').trim();
                        var vText = (tds[2].innerText || tds[2].textContent || '').replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();

                        if (dText && dText.toUpperCase() !== 'TOTAL' && dText.toUpperCase() !== 'FORMA DE PAGAMENTO' && vText && vText !== '0,00') {
                            itens.push({ descricao: dText, qtNfs: qText, valor: vText });
                        }
                    }
                }
            } catch(e) {}

            if (itens.length > 0) return itens;

            // Estratégia 2: Regex no innerText do documento
            try {
                var text = (doc.body ? doc.body.innerText || doc.body.textContent : '') || '';
                var lines = text.split('\\n');
                for (var l = 0; l < lines.length; l++) {
                    var line = lines[l].replace(/\\u00a0/g, ' ').replace(/\\s+/g, ' ').trim();
                    if (!line || line.toUpperCase().indexOf('TOTAL') === 0 || line.toUpperCase().indexOf('FORMA') === 0) continue;

                    var match = line.match(/^(.+?)\\s+(\\d+)\\s+([\\d\\.\\,]+)$/);
                    if (match) {
                        var desc = match[1].trim();
                        var qt = match[2].trim();
                        var val = match[3].trim();
                        if (desc && val && val !== '0,00') {
                            itens.push({ descricao: desc, qtNfs: qt, valor: val });
                        }
                    }
                }
            } catch(e) {}

            return itens;
        }
    """

    @staticmethod
    def normalizar_mapa(mapa):
        """Normaliza e valida o número do mapa."""
        valor = str(mapa or "").strip()
        if valor.endswith(".0"):
            valor = valor[:-2]
        valor = valor.replace(".", "").replace(",", "")
        if not valor or valor == "0":
            raise ValueError("Mapa deve ser informado e diferente de zero.")
        if not valor.isdigit():
            raise ValueError(f"Mapa invalido: {mapa}")
        return valor

    def _garantir_frame_rotina(self):
        """Garante que a sessão do Selenium esteja focada no FRAME_ROTINA."""
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
        except Exception as e:
            self.logger.debug(f"03030702 | Aviso ao alternar para FRAME_ROTINA: {e}")

    def _entrar_iframe_saida_nativo(self):
        """Navega nativamente para o iFrameSaida através do Selenium."""
        self._garantir_frame_rotina()
        try:
            self.driver.switch_to.frame("iFrameSaida")
            return True
        except Exception:
            try:
                self.driver.switch_to.frame(0)
                return True
            except Exception:
                return False

    def _entrar_iframe_retorno_nativo(self):
        """Navega nativamente para o iFrameRetorno através do Selenium."""
        self._garantir_frame_rotina()
        try:
            self.driver.switch_to.frame("iFrameRetorno")
            return True
        except Exception:
            try:
                self.driver.switch_to.frame(1)
                return True
            except Exception:
                return False

    def _esperar_campo_habilitado_js(self, nome_elemento, timeout_segundos=15):
        """Aguarda via JS até que o campo esteja habilitado para edição."""
        script = self.JS_RECURSIVE_FRAME_FINDER + f"""
            var r = getRotinaWin();
            if (!r || !r.document) return false;
            var el = r.document.getElementsByName('{nome_elemento}')[0];
            if (!el) return false;
            if (el.disabled) return false;
            if (el.readOnly) return false;
            if (el.style.display === 'none' || el.style.visibility === 'hidden') return false;
            return true;
        """
        fim = time.time() + timeout_segundos
        while time.time() < fim:
            try:
                self._garantir_frame_rotina()
                pronto = self.driver.execute_script(script)
                if pronto:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _lidar_com_alerta_ie(self):
        """Captura e aceita alerta se presente."""
        try:
            alerta = self.driver.switch_to.alert
            texto = alerta.text
            alerta.accept()
            return texto
        except NoAlertPresentException:
            return None
        except Exception:
            return None

    def _esperar_iframes_carregados(self, timeout_segundos=15):
        """
        Aguarda o carregamento do iFrameRetorno via motor duplo (JS + Native Switch).
        """
        fim = time.time() + timeout_segundos
        script_js = self.JS_RECURSIVE_FRAME_FINDER + """
            try {
                var ctx = buscarDocumentoPorElemento(function(w, d) {
                    try {
                        if (d.all && (d.all('lista') || d.all('textcod00') || d.all('textcod000') || d.all('textcod0'))) return true;
                        if (d.getElementById('lista')) return true;
                        var html = (d.body ? d.body.innerHTML : '') || '';
                        if (html.indexOf('name=lista') !== -1 || html.indexOf('textcod') !== -1) return true;
                    } catch(e) {}
                    return false;
                });
                if (!ctx || !ctx.doc) return { pronto: false };
                var doc = ctx.doc;
                var lista = doc.all ? doc.all('lista') : doc.getElementById('lista');
                if (lista && lista.rows && lista.rows.length > 0) return { pronto: true };
                return { pronto: false };
            } catch (e) {
                return { pronto: false };
            }
        """
        while time.time() < fim:
            try:
                self._garantir_frame_rotina()
                alerta = self._lidar_com_alerta_ie()
                if alerta:
                    return {"pronto": False, "alerta": alerta}

                res = self.driver.execute_script(script_js)
                if res and isinstance(res, dict) and res.get("pronto"):
                    return res

                # Motor 2: Nativo
                if self._entrar_iframe_retorno_nativo():
                    pronto_nat = self.driver.execute_script("return !!(document.getElementById('lista') || document.all['lista']);")
                    self._garantir_frame_rotina()
                    if pronto_nat:
                        return {"pronto": True}
            except Exception:
                pass
            time.sleep(0.5)

        return {"pronto": False, "alerta": None}

    def _instalar_interceptador_alertas_salvar(self):
        """
        Instala interceptador via JS para resolver caixas de diálogo msgbxSimNao / confirm ao salvar.
        """
        script = self.JS_RECURSIVE_FRAME_FINDER + """
            var r = getRotinaWin();
            var targetWin = r || window;

            targetWin.confirm = function(msg) {
                var txt = (msg || '').toLowerCase();
                if (txt.indexOf('diferen') !== -1 && txt.indexOf('nao exist') === -1 && txt.indexOf('nao ha') === -1) {
                    return false;
                }
                return true;
            };

            targetWin.msgbxSimNao = function(titulo, mensagem, fnSim, fnNao) {
                var txt = (String(titulo || '') + ' ' + String(mensagem || '')).toLowerCase();
                var simCb = typeof fnSim === 'function' ? fnSim : null;
                var naoCb = typeof fnNao === 'function' ? fnNao : null;

                if (txt.indexOf('diferen') !== -1 && txt.indexOf('nao exist') === -1 && txt.indexOf('nao ha') === -1) {
                    if (naoCb) {
                        setTimeout(function() { naoCb(); }, 50);
                    } else if (simCb) {
                        setTimeout(function() { simCb(); }, 50);
                    }
                } else {
                    if (simCb) {
                        setTimeout(function() { simCb(); }, 50);
                    } else if (naoCb) {
                        setTimeout(function() { naoCb(); }, 50);
                    }
                }
            };
        """
        try:
            self._garantir_frame_rotina()
            self.driver.execute_script(script)
        except Exception as e:
            self.logger.debug(f"03030702 | Falha ao instalar interceptador de alertas via JS: {e}")

    def carregar_mapa(self, mapa, ponto_apoio=None, auto_equilibrar=True):
        """
        Carrega um mapa na rotina 03030702, aguarda a renderizacao dos dados e obrigatoriamente
        digita todas as contas pendentes da Saída no Retorno ANTES de finalizar a carga.
        """
        mapa_norm = self.normalizar_mapa(mapa)
        try:
            self._garantir_frame_rotina()
            self.logger.info(f"03030702 | Carregando mapa: {mapa_norm} via JS...")

            if not self._esperar_campo_habilitado_js("numeroMapa", 10):
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message="Campo 'numeroMapa' nao disponivel para digitacao.",
                )

            self._instalar_interceptador_alertas_salvar()

            script_carga = self.JS_RECURSIVE_FRAME_FINDER + f"""
                var r = getRotinaWin();
                if (r && r.document) {{
                    var cmp = r.document.getElementsByName('numeroMapa')[0];
                    if (cmp) cmp.value = '{mapa_norm}';
                    if (typeof r.CarregarMapa === 'function') r.CarregarMapa();
                }}
            """
            self.driver.execute_script(script_carga)

            self.logger.info("03030702 | Aguardando carregamento do mapa e renderizacao dos dados...")
            time.sleep(3.0)

            status_iframes = self._esperar_iframes_carregados(timeout_segundos=15)
            if not status_iframes.get("pronto"):
                alerta_texto = status_iframes.get("alerta") or self._lidar_com_alerta_ie()
                if alerta_texto:
                    return ExecutionResult(
                        status=ExecutionStatus.BUSINESS_FAILURE,
                        message=f"Alerta retornado ao carregar mapa: {alerta_texto}",
                    )
                self.logger.warning("03030702 | iFrameRetorno demorou a responder, prosseguindo com verificacao.")

            if auto_equilibrar:
                self.logger.info("03030702 | EXECUTANDO DIGITACAO DINAMICA E OBRIGATORIA DAS CONTAS NO RETORNO...")
                self.equilibrar_contas_saida()

            resumo = self.obter_resumo_diferencas()
            self.logger.info(f"03030702 | Mapa {mapa_norm} carregado e conferido. Resumo de Diferencas: {resumo}")

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Mapa {mapa_norm} carregado e conferido com sucesso na 03030702.",
                metadata={"mapa": mapa_norm, "resumo": resumo},
            )

        except Exception as e:
            self.logger.error(f"03030702 | Erro inesperado ao carregar mapa {mapa_norm}: {e}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao carregar mapa {mapa_norm}: {str(e)}",
            )

    def obter_itens_saida(self, timeout_segundos=20):
        """
        Lê a Saída pelo MESMO caminho usado pelo JavaScript nativo do Promax.

        O HTML do iFrameRetorno mostra que o próprio Promax acessa a Saída por:
            window.parent.document.parentWindow.parent.rotina
                .document.frames.iFrameSaida.document

        Por isso a leitura é executada de dentro do iFrameRetorno, evitando
        depender da árvore de frames que o Selenium/IE Mode expõe.
        """

        script = r"""
            function limpar(v) {
                if (v === null || typeof v === 'undefined') return '';
                return String(v)
                    .replace(/\u00a0/g, ' ')
                    .replace(/\s+/g, ' ')
                    .replace(/^\s+|\s+$/g, '');
            }

            function texto(el) {
                if (!el) return '';
                var v = '';
                try { v = el.innerText; } catch(e) {}
                if (!v) {
                    try { v = el.textContent; } catch(e) {}
                }
                if (!v) {
                    try { v = el.value; } catch(e) {}
                }
                return limpar(v);
            }

            function documentoSaida() {
                var d = null;

                // Caminho EXATO encontrado no JavaScript do Promax.
                try {
                    d = window.parent.document.parentWindow.parent.rotina
                        .document.frames.iFrameSaida.document;
                    if (d) return { doc: d, origem: 'promax.exato' };
                } catch(e) {}

                // Variações para IE/IEDriver/IE Mode.
                try {
                    d = window.parent.document.parentWindow.parent.rotina
                        .document.frames['iFrameSaida'].document;
                    if (d) return { doc: d, origem: 'promax.frames[]' };
                } catch(e) {}

                try {
                    var r = window.parent.document.parentWindow.parent.rotina;
                    var f = r.document.getElementById('iFrameSaida');
                    if (f && f.contentWindow && f.contentWindow.document) {
                        return { doc: f.contentWindow.document, origem: 'promax.contentWindow' };
                    }
                } catch(e) {}

                try {
                    d = window.parent.frames['iFrameSaida'].document;
                    if (d) return { doc: d, origem: 'parent.frames' };
                } catch(e) {}

                try {
                    d = window.top.frames['iFrameSaida'].document;
                    if (d) return { doc: d, origem: 'top.frames' };
                } catch(e) {}

                return { doc: null, origem: 'nao-localizado' };
            }

            function valorMonetario(v) {
                v = limpar(v);
                if (!v) return false;
                return /^-?[0-9\.]+(?:,[0-9]{1,2})?-?$/.test(v);
            }

            var ctx = documentoSaida();
            var doc = ctx.doc;

            if (!doc) {
                return {
                    ok: false,
                    origem: ctx.origem,
                    erro: 'Documento do iFrameSaida nao localizado pelo caminho nativo do Promax',
                    itens: []
                };
            }

            var itens = [];
            var vistos = {};

            function adicionar(desc, qt, valor, origemLinha) {
                desc = limpar(desc);
                qt = limpar(qt);
                valor = limpar(valor);

                var up = desc.toUpperCase();

                if (!desc) return;
                if (up === 'TOTAL') return;
                if (up === 'DESCRIÇÃO' || up === 'DESCRICAO') return;
                if (up === 'SAÍDA' || up === 'SAIDA') return;
                if (up.indexOf('FORMA DE PAGAMENTO') >= 0) return;
                if (!valorMonetario(valor)) return;

                // Não filtra por categoria conhecida.
                // Qualquer linha válida da Saída com descrição + quantidade + valor
                // deve ser lida. Assim categorias como CREDITO EM CONTA, TROCA,
                // A VISTA e futuras categorias também serão identificadas.

                var chave = up + '|' + qt + '|' + valor;
                if (vistos[chave]) return;
                vistos[chave] = true;

                itens.push({
                    descricao: desc,
                    qtNfs: qt,
                    valor: valor,
                    origem: origemLinha
                });
            }

            // 1) DOM vivo da área listagemSaida.
            try {
                var div = doc.getElementById('listagemSaida');
                if (!div && doc.all) {
                    try { div = doc.all['listagemSaida']; } catch(e) {}
                }

                if (div) {
                    var trsDiv = div.getElementsByTagName('TR');
                    if (!trsDiv || !trsDiv.length) {
                        trsDiv = div.getElementsByTagName('tr');
                    }

                    for (var i = 0; trsDiv && i < trsDiv.length; i++) {
                        var cells = trsDiv[i].cells;
                        if (!cells || cells.length < 3) continue;

                        adicionar(
                            texto(cells[0]),
                            texto(cells[1]),
                            texto(cells[2]),
                            'listagemSaida'
                        );
                    }
                }
            } catch(e) {}

            // 2) Todas as linhas do documento, porque o Promax pode injetar
            // a tabela fora do DIV original.
            if (!itens.length) {
                try {
                    var trs = doc.getElementsByTagName('TR');
                    if (!trs || !trs.length) {
                        trs = doc.getElementsByTagName('tr');
                    }

                    for (var j = 0; trs && j < trs.length; j++) {
                        var cells2 = trs[j].cells;
                        if (!cells2 || cells2.length < 3) continue;

                        adicionar(
                            texto(cells2[0]),
                            texto(cells2[1]),
                            texto(cells2[2]),
                            'document.TR'
                        );
                    }
                } catch(e) {}
            }

            // 3) Fallback por texto visível.
            if (!itens.length) {
                try {
                    var corpo = '';
                    if (doc.body) {
                        corpo = doc.body.innerText || doc.body.textContent || '';
                    }

                    var linhas = String(corpo).split(/\r?\n/);
                    for (var k = 0; k < linhas.length; k++) {
                        var ln = limpar(linhas[k]);
                        if (!ln) continue;

                        var m = ln.match(/^(.+?)\s+(\d+)\s+(-?[0-9\.]+(?:,[0-9]{1,2})?-?)$/);
                        if (m) {
                            adicionar(m[1], m[2], m[3], 'body.innerText');
                        }
                    }
                } catch(e) {}
            }

            var totalSaida = '';
            try {
                if (doc.all && doc.all.total) totalSaida = doc.all.total.value;
            } catch(e) {}

            var htmlListagem = '';
            try {
                var ld = doc.getElementById('listagemSaida');
                if (ld) htmlListagem = ld.innerHTML || '';
            } catch(e) {}

            var bodyText = '';
            try {
                if (doc.body) bodyText = doc.body.innerText || '';
            } catch(e) {}

            return {
                ok: itens.length > 0,
                origem: ctx.origem,
                itens: itens,
                totalSaida: limpar(totalSaida),
                htmlListagem: String(htmlListagem || '').substring(0, 2000),
                bodyText: String(bodyText || '').substring(0, 1000)
            };
        """

        fim = time.time() + timeout_segundos
        ultimo = {}

        while time.time() < fim:
            try:
                if not self._entrar_iframe_retorno_nativo():
                    self.logger.debug(
                        "03030702 | Ainda nao foi possivel entrar no iFrameRetorno para ler a Saida."
                    )
                    time.sleep(0.5)
                    continue

                resultado = self.driver.execute_script(script) or {}
                self._garantir_frame_rotina()

                if isinstance(resultado, dict):
                    ultimo = resultado
                    itens = resultado.get("itens") or []

                    if itens:
                        limpos = [
                            {
                                "descricao": str(x.get("descricao", "")).strip(),
                                "qtNfs": str(x.get("qtNfs", "")).strip(),
                                "valor": str(x.get("valor", "")).strip(),
                            }
                            for x in itens
                        ]

                        self.logger.info(
                            "03030702 | Saida localizada pelo caminho nativo do Promax "
                            f"| origem={resultado.get('origem')} "
                            f"| total={resultado.get('totalSaida')} "
                            f"| itens={limpos}"
                        )
                        return limpos

            except Exception as e:
                try:
                    self._garantir_frame_rotina()
                except Exception:
                    pass
                self.logger.debug(
                    "03030702 | Tentativa de leitura direta da Saida falhou: "
                    f"{type(e).__name__}: {e}"
                )

            time.sleep(0.5)

        try:
            self._garantir_frame_rotina()
        except Exception:
            pass

        self.logger.error(
            "03030702 | Nao foi possivel ler os itens da Saida. "
            f"Ultimo diagnostico={ultimo}"
        )
        return []

    def obter_resumo_diferencas(self):
        """
        Lê Produtos/Vasilhames/Contas/Total diretamente do parent do
        iFrameRetorno. O próprio CalculaTotal() do Promax escreve nesses campos
        através de window.parent.document.all.<campo>.
        """
        script = r"""
            function pegar(doc, nome) {
                if (!doc) return '';
                var el = null;

                try {
                    if (doc.all) el = doc.all[nome] || doc.all(nome);
                } catch(e) {}

                if (!el) {
                    try {
                        var arr = doc.getElementsByName(nome);
                        if (arr && arr.length) el = arr[0];
                    } catch(e) {}
                }

                if (!el) {
                    try { el = doc.getElementById(nome); } catch(e) {}
                }

                if (!el) return '';

                var v = '';
                try { v = el.value; } catch(e) {}
                if (v === null || typeof v === 'undefined' || v === '') {
                    try { v = el.innerText; } catch(e) {}
                }

                return String(v || '').replace(/^\s+|\s+$/g, '');
            }

            var p = null;
            try { p = window.parent.document; } catch(e) {}

            return {
                produtos: pegar(p, 'produtos'),
                vasilhames: pegar(p, 'vasilhames'),
                contas: pegar(p, 'contas'),
                total: pegar(p, 'total'),
                dataEmi: pegar(p, 'dataEmi'),
                dataDeposito: pegar(p, 'dataDeposito')
            };
        """

        try:
            if not self._entrar_iframe_retorno_nativo():
                return {}

            resultado = self.driver.execute_script(script) or {}
            self._garantir_frame_rotina()

            return resultado if isinstance(resultado, dict) else {}

        except Exception as e:
            try:
                self._garantir_frame_rotina()
            except Exception:
                pass
            self.logger.debug(
                f"03030702 | Erro ao obter resumo de diferencas pelo parent do Retorno: {e}"
            )
            return {}

    def lancar_conta_retorno(self, codigo_conta, valor, num_vale=0):
        """
        Lança uma conta reproduzindo o fluxo NATIVO do Promax.

        Código:
            textcodNNN.value = codigo
            -> CarregaCondPagto(textcodNNN)
            -> opcao=3
            -> EnviarFormulario()
            -> postback

        Valor:
            textvalorNNN.value = valor
            -> AdicionaLista() quando necessário
            -> ValorCampo()
            -> CalculaTotal()
            -> ControleValor()

        Não tenta lançar código 0, pois CarregaCondPagto() do próprio Promax
        retorna false para código zero. Vasilhame é tratado como linha automática.
        """

        codigo = str(codigo_conta or "").strip()
        num_vale_str = str(num_vale or "0").strip()

        if codigo == "0":
            self.logger.warning(
                "03030702 | BLOQUEADO: tentativa de lancamento manual do codigo 0. "
                "Vasilhame deve vir automaticamente no Retorno."
            )
            return False

        if isinstance(valor, (int, float)):
            valor_str = f"{float(valor):.2f}".replace(".", ",")
        else:
            valor_str = str(valor or "").strip().replace("R$", "").replace(" ", "")
            if "," in valor_str:
                valor_str = valor_str.replace(".", "")
            elif "." in valor_str:
                partes = valor_str.rsplit(".", 1)
                if len(partes) == 2 and len(partes[1]) <= 2:
                    valor_str = partes[0].replace(".", "") + "," + partes[1]
                else:
                    valor_str = valor_str.replace(".", "")
            if "," not in valor_str:
                valor_str += ",00"

        self.logger.info(
            f"03030702 | LANCAMENTO NATIVO | Codigo={codigo} | Valor={valor_str}"
        )

        script_escolher_linha = r"""
            function pad3(n) {
                n = parseInt(n, 10);
                if (n < 10) return '00' + n;
                if (n < 100) return '0' + n;
                return String(n);
            }

            var lista = null;
            try { lista = document.all.lista; } catch(e) {}
            if (!lista) {
                try { lista = document.getElementById('lista'); } catch(e) {}
            }

            if (!lista) {
                return { ok: false, erro: 'TABLE lista nao localizada' };
            }

            var primeiroVazio = null;

            for (var i = 0; i < lista.rows.length; i++) {
                var seq = pad3(i);
                var cod = null;

                try { cod = document.all['textcod' + seq]; } catch(e) {}
                if (!cod) {
                    try {
                        cod = document.getElementsByName('textcod' + seq)[0];
                    } catch(e) {}
                }

                if (!cod) continue;

                var atual = String(cod.value || '').replace(/^\s+|\s+$/g, '');

                if (atual === arguments[0]) {
                    return {
                        ok: true,
                        seq: seq,
                        existente: true,
                        vazio: false
                    };
                }

                if (primeiroVazio === null && (atual === '' || atual === '0')) {
                    // Código 0 com descrição Vasilhame NÃO é linha vazia.
                    var desc = '';
                    try {
                        desc = lista.rows[i].cells[1].innerText || '';
                    } catch(e) {}

                    desc = String(desc || '')
                        .replace(/\u00a0/g, ' ')
                        .replace(/^\s+|\s+$/g, '');

                    if (!desc) {
                        primeiroVazio = seq;
                    }
                }
            }

            if (primeiroVazio !== null) {
                return {
                    ok: true,
                    seq: primeiroVazio,
                    existente: false,
                    vazio: true
                };
            }

            // Se não houver linha vazia, usa o próprio mecanismo da tela.
            try {
                if (typeof AdicionaLista === 'function') {
                    var antes = lista.rows.length;

                    // Para evitar ProximaExiste() depender de um activeElement estranho,
                    // foca o último campo de valor/código disponível antes de adicionar.
                    if (antes > 0) {
                        var ult = pad3(antes - 1);
                        var foco = document.all['textvalor' + ult] || document.all['textcod' + ult];
                        if (foco && foco.focus) foco.focus();
                    }

                    AdicionaLista('', '', '', '', '');

                    var depois = lista.rows.length;
                    if (depois > antes) {
                        var novaSeq = pad3(depois - 1);

                        // AdicionaLista cria campo vazio com value="0".
                        // Limpa imediatamente para não parecer lançamento de
                        // Vasilhame/código 0 e para a linha continuar realmente vazia.
                        try {
                            var novoCod = document.all['textcod' + novaSeq];
                            if (novoCod) novoCod.value = '';
                        } catch(e) {}

                        return {
                            ok: true,
                            seq: novaSeq,
                            existente: false,
                            vazio: true,
                            adicionada: true
                        };
                    }
                }
            } catch(e) {}

            return {
                ok: false,
                erro: 'Nenhuma linha vazia disponivel e AdicionaLista nao criou nova linha',
                linhas: lista.rows.length
            };
        """

        script_disparar_codigo = r"""
            var seq = arguments[0];
            var codigo = arguments[1];
            var numVale = arguments[2];

            var cmp = null;
            try { cmp = document.all['textcod' + seq]; } catch(e) {}
            if (!cmp) {
                try { cmp = document.getElementsByName('textcod' + seq)[0]; } catch(e) {}
            }

            if (!cmp) {
                return { ok: false, erro: 'textcod' + seq + ' nao localizado' };
            }

            cmp.disabled = false;
            cmp.readOnly = false;
            cmp.value = codigo;

            try {
                var nv = document.all['textnumVale' + seq];
                if (nv && numVale && numVale !== '0') nv.value = numVale;
            } catch(e) {}

            try { cmp.focus(); } catch(e) {}
            try { cmp.select(); } catch(e) {}

            if (typeof CarregaCondPagto !== 'function') {
                return {
                    ok: false,
                    erro: 'Funcao CarregaCondPagto nao existe no iFrameRetorno'
                };
            }

            // Retorna ao Selenium antes do postback.
            setTimeout(function() {
                try {
                    CarregaCondPagto(cmp);
                } catch(e) {}
            }, 30);

            return {
                ok: true,
                seq: seq,
                codigo: cmp.value,
                disparou: true
            };
        """

        script_estado_codigo = r"""
            function pad3(n) {
                n = parseInt(n, 10);
                if (n < 10) return '00' + n;
                if (n < 100) return '0' + n;
                return String(n);
            }

            var codigo = arguments[0];
            var lista = document.all.lista || document.getElementById('lista');
            if (!lista) return { ok: false };

            for (var i = 0; i < lista.rows.length; i++) {
                var seq = pad3(i);
                var cod = document.all['textcod' + seq];
                if (!cod) continue;

                if (String(cod.value || '').replace(/^\s+|\s+$/g, '') === codigo) {
                    var desc = '';
                    try {
                        desc = lista.rows[i].cells[1].innerText || '';
                    } catch(e) {}

                    var val = document.all['textvalor' + seq];

                    return {
                        ok: true,
                        seq: seq,
                        descricao: String(desc || '')
                            .replace(/\u00a0/g, ' ')
                            .replace(/^\s+|\s+$/g, ''),
                        valorExiste: !!val,
                        valorDisabled: val ? !!val.disabled : true,
                        valorAtual: val ? String(val.value || '') : ''
                    };
                }
            }

            return { ok: false };
        """

        script_preencher_valor = r"""
            var seq = arguments[0];
            var valorInformado = arguments[1];
            var numVale = arguments[2];

            var cmpCod = document.all['textcod' + seq];
            var cmpVal = document.all['textvalor' + seq];

            if (!cmpCod) {
                return { ok: false, erro: 'textcod' + seq + ' nao localizado' };
            }

            if (!cmpVal) {
                return { ok: false, erro: 'textvalor' + seq + ' nao localizado' };
            }

            cmpVal.disabled = false;
            cmpVal.readOnly = false;

            try {
                var nv = document.all['textnumVale' + seq];
                if (nv && numVale && numVale !== '0') nv.value = numVale;
            } catch(e) {}

            try { cmpVal.focus(); } catch(e) {}
            try { cmpVal.select(); } catch(e) {}

            cmpVal.value = valorInformado;

            // NÃO cria a próxima linha antecipadamente.
            // AdicionaLista('',...) gera um textcod com valor "0" no Promax.
            // A próxima linha só será criada no momento em que houver outra
            // categoria realmente pendente para lançar.
            // onChange nativo do textvalor.
            try {
                if (typeof ValorCampo === 'function') {
                    ValorCampo(cmpVal, '9.999.999.999,99');
                }
            } catch(e) {}

            try {
                if (typeof CalculaTotal === 'function') {
                    CalculaTotal();
                }
            } catch(e) {}

            try {
                if (typeof ControleValor === 'function') {
                    ControleValor(seq, cmpVal.value);
                }
            } catch(e) {}

            // Recalcula após ControleValor, pois algumas contas podem alterar estado.
            try {
                if (typeof CalculaTotal === 'function') {
                    CalculaTotal();
                }
            } catch(e) {}

            return {
                ok: true,
                seq: seq,
                codigo: String(cmpCod.value || ''),
                valor: String(cmpVal.value || ''),
                disabled: !!cmpVal.disabled,
                totalRetorno: document.all.totalRetorno
                    ? String(document.all.totalRetorno.value || '')
                    : ''
            };
        """

        try:
            # ----------------------------------------------------------
            # 1. Localiza a linha
            # ----------------------------------------------------------
            if not self._entrar_iframe_retorno_nativo():
                self.logger.error("03030702 | iFrameRetorno nao localizado.")
                return False

            escolha = self.driver.execute_script(script_escolher_linha, codigo) or {}

            if not isinstance(escolha, dict) or not escolha.get("ok"):
                self.logger.error(
                    f"03030702 | Nao foi possivel escolher linha para conta {codigo}: {escolha}"
                )
                self._garantir_frame_rotina()
                return False

            seq = str(escolha.get("seq", "")).zfill(3)
            existente = bool(escolha.get("existente"))

            self.logger.info(
                f"03030702 | Conta {codigo} usara linha {seq} "
                f"| existente={existente}"
            )

            # ----------------------------------------------------------
            # 2. Se for nova, dispara CarregaCondPagto -> postback
            # ----------------------------------------------------------
            if not existente:
                disparo = self.driver.execute_script(
                    script_disparar_codigo,
                    seq,
                    codigo,
                    num_vale_str,
                ) or {}

                self.logger.info(
                    f"03030702 | CarregaCondPagto preparado para conta {codigo}: {disparo}"
                )

                if not isinstance(disparo, dict) or not disparo.get("ok"):
                    self._garantir_frame_rotina()
                    return False

                # Aguarda o setTimeout disparar e o CGI reconstruir o frame.
                time.sleep(0.6)

                fim_postback = time.time() + 20
                estado = {}

                while time.time() < fim_postback:
                    try:
                        self._garantir_frame_rotina()

                        if not self._entrar_iframe_retorno_nativo():
                            time.sleep(0.3)
                            continue

                        estado = self.driver.execute_script(
                            script_estado_codigo,
                            codigo,
                        ) or {}

                        # A conta só está pronta quando voltou com a linha e
                        # com o campo de valor criado.
                        if (
                            isinstance(estado, dict)
                            and estado.get("ok")
                            and estado.get("valorExiste")
                        ):
                            seq = str(estado.get("seq", seq)).zfill(3)

                            self.logger.info(
                                "03030702 | Conta retornou do postback "
                                f"| codigo={codigo} | linha={seq} "
                                f"| descricao={estado.get('descricao')} "
                                f"| valorDisabled={estado.get('valorDisabled')}"
                            )
                            break

                    except Exception:
                        pass

                    time.sleep(0.35)
                else:
                    self._garantir_frame_rotina()
                    self.logger.error(
                        f"03030702 | Timeout aguardando retorno de CarregaCondPagto "
                        f"para conta {codigo}. Ultimo estado={estado}"
                    )
                    return False

            # ----------------------------------------------------------
            # 3. Entra novamente e preenche o valor
            # ----------------------------------------------------------
            self._garantir_frame_rotina()

            if not self._entrar_iframe_retorno_nativo():
                return False

            estado_final_codigo = self.driver.execute_script(
                script_estado_codigo,
                codigo,
            ) or {}

            if isinstance(estado_final_codigo, dict) and estado_final_codigo.get("ok"):
                seq = str(estado_final_codigo.get("seq", seq)).zfill(3)

            preenchimento = self.driver.execute_script(
                script_preencher_valor,
                seq,
                valor_str,
                num_vale_str,
            ) or {}

            self.logger.info(
                f"03030702 | Resultado do preenchimento da conta {codigo}: {preenchimento}"
            )

            if not isinstance(preenchimento, dict) or not preenchimento.get("ok"):
                self._garantir_frame_rotina()
                return False

            valor_final = str(preenchimento.get("valor", "")).strip()

            self._garantir_frame_rotina()

            if not valor_final or valor_final in ("0", "0,00"):
                self.logger.error(
                    f"03030702 | Valor nao permaneceu preenchido na conta {codigo}. "
                    f"Resultado={preenchimento}"
                )
                return False

            self.logger.info(
                f"03030702 | CONTA {codigo} PREENCHIDA COM SUCESSO "
                f"| linha={seq} | valor={valor_final}"
            )
            return True

        except Exception as e:
            try:
                self._garantir_frame_rotina()
            except Exception:
                pass

            self.logger.error(
                f"03030702 | ERRO AO LANCAR CONTA {codigo}: "
                f"{type(e).__name__}: {e}"
            )
            return False


    def _adicionar_linha_vazia_retorno(self):
        """Adiciona uma linha vazia no Retorno apos equilibrar as contas."""
        script = r"""
            function pad3(n) {
                n = parseInt(n, 10);
                if (n < 10) return '00' + n;
                if (n < 100) return '0' + n;
                return String(n);
            }

            var lista = document.all.lista || document.getElementById('lista');
            if (!lista) return { ok: false, erro: 'TABLE lista nao localizada' };
            if (typeof AdicionaLista !== 'function') {
                return { ok: false, erro: 'AdicionaLista nao localizada' };
            }

            var antes = lista.rows.length;
            if (antes > 0) {
                var ult = pad3(antes - 1);
                var foco = document.all['textvalor' + ult] || document.all['textcod' + ult];
                try { if (foco && foco.focus) foco.focus(); } catch(e) {}
            }

            AdicionaLista('', '', '', '', '');

            var depois = lista.rows.length;
            if (depois <= antes) {
                return { ok: false, erro: 'AdicionaLista nao criou nova linha', antes: antes, depois: depois };
            }

            var seq = pad3(depois - 1);
            try {
                var cod = document.all['textcod' + seq];
                if (cod) cod.value = '';
            } catch(e) {}
            try {
                var valor = document.all['textvalor' + seq];
                if (valor) valor.value = '';
            } catch(e) {}

            return { ok: true, seq: seq, antes: antes, depois: depois };
        """

        try:
            if not self._entrar_iframe_retorno_nativo():
                self.logger.warning(
                    "03030702 | Nao foi possivel adicionar linha vazia: iFrameRetorno nao localizado."
                )
                return False

            resultado = self.driver.execute_script(script) or {}
            self._garantir_frame_rotina()

            if not isinstance(resultado, dict) or not resultado.get("ok"):
                self.logger.warning(
                    f"03030702 | Linha vazia nao adicionada apos equilibrio: {resultado}"
                )
                return False

            self.logger.info(
                f"03030702 | Linha vazia adicionada apos equilibrio: {resultado}"
            )
            return True

        except Exception as e:
            try:
                self._garantir_frame_rotina()
            except Exception:
                pass
            self.logger.warning(
                f"03030702 | Erro ao adicionar linha vazia apos equilibrio: {e}"
            )
            return False


    def obter_contas_retorno(self):
        """Retorna o estado vivo das linhas do TABLE lista no iFrameRetorno."""
        script = r"""
            function pad3(n) {
                n = parseInt(n, 10);
                if (n < 10) return '00' + n;
                if (n < 100) return '0' + n;
                return String(n);
            }

            var lista = document.all.lista || document.getElementById('lista');
            if (!lista) return [];

            var saida = [];

            for (var i = 0; i < lista.rows.length; i++) {
                var seq = pad3(i);
                var cod = document.all['textcod' + seq];
                var val = document.all['textvalor' + seq];

                var desc = '';
                try {
                    desc = lista.rows[i].cells[1].innerText || '';
                } catch(e) {}

                desc = String(desc || '')
                    .replace(/\u00a0/g, ' ')
                    .replace(/^\s+|\s+$/g, '');

                var codigoAtual = cod
                    ? String(cod.value || '').replace(/^\s+|\s+$/g, '')
                    : '';

                var valorAtual = val
                    ? String(val.value || '').replace(/^\s+|\s+$/g, '')
                    : '';

                // O Promax usa "0" como valor padrão de uma linha recém-criada.
                // Sem descrição, isso NÃO é Vasilhame nem conta válida.
                var linhaVazia = (!desc && (codigoAtual === '' || codigoAtual === '0'));

                saida.push({
                    seq: seq,
                    codigo: linhaVazia ? '' : codigoAtual,
                    descricao: desc,
                    valor: valorAtual,
                    valorDisabled: val ? !!val.disabled : null,
                    linhaVazia: linhaVazia
                });
            }

            return saida;
        """

        try:
            if not self._entrar_iframe_retorno_nativo():
                return []

            linhas = self.driver.execute_script(script) or []
            self._garantir_frame_rotina()
            return linhas if isinstance(linhas, list) else []

        except Exception as e:
            try:
                self._garantir_frame_rotina()
            except Exception:
                pass

            self.logger.debug(
                f"03030702 | Falha ao ler linhas atuais do Retorno: {e}"
            )
            return []

    def _extrair_dom_estruturado_03030702(self, incluir_html=False):
        """Retorna um snapshot estruturado do DOM vivo da rotina e seus iframes."""
        script = self.JS_RECURSIVE_FRAME_FINDER + r"""
            var incluirHtml = arguments[0] === true;

            function limpar(v) {
                if (v === null || typeof v === 'undefined') return '';
                return String(v)
                    .replace(/\u00a0/g, ' ')
                    .replace(/\s+/g, ' ')
                    .replace(/^\s+|\s+$/g, '');
            }

            function texto(el) {
                if (!el) return '';
                var v = '';
                try { v = el.innerText; } catch(e) {}
                if (!v) {
                    try { v = el.textContent; } catch(e) {}
                }
                if (!v) {
                    try { v = el.value; } catch(e) {}
                }
                return limpar(v);
            }

            function valor(el) {
                if (!el) return '';
                var v = '';
                try { v = el.value; } catch(e) {}
                if (v === null || typeof v === 'undefined' || v === '') {
                    try { v = el.innerText; } catch(e) {}
                }
                if (v === null || typeof v === 'undefined' || v === '') {
                    try { v = el.textContent; } catch(e) {}
                }
                return limpar(v);
            }

            function nomeTag(el) {
                try { return String(el.tagName || '').toLowerCase(); } catch(e) {}
                return '';
            }

            function coletarOpcoes(selectEl) {
                var saida = [];
                try {
                    for (var i = 0; i < selectEl.options.length; i++) {
                        var op = selectEl.options[i];
                        saida.push({
                            index: i,
                            value: limpar(op.value),
                            text: texto(op),
                            selected: !!op.selected
                        });
                    }
                } catch(e) {}
                return saida;
            }

            function coletarCampos(doc) {
                var tags = ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'];
                var campos = [];

                for (var t = 0; t < tags.length; t++) {
                    var elementos = [];
                    try { elementos = doc.getElementsByTagName(tags[t]); } catch(e) {}

                    for (var i = 0; elementos && i < elementos.length; i++) {
                        var el = elementos[i];
                        var item = {
                            ordem: campos.length,
                            tag: nomeTag(el),
                            id: '',
                            name: '',
                            type: '',
                            value: '',
                            text: '',
                            disabled: null,
                            readOnly: null,
                            checked: null,
                            selectedIndex: null
                        };

                        try { item.id = limpar(el.id); } catch(e) {}
                        try { item.name = limpar(el.name); } catch(e) {}
                        try { item.type = limpar(el.type); } catch(e) {}
                        try { item.value = valor(el); } catch(e) {}
                        try { item.text = texto(el); } catch(e) {}
                        try { item.disabled = !!el.disabled; } catch(e) {}
                        try { item.readOnly = !!el.readOnly; } catch(e) {}
                        try {
                            if (typeof el.checked !== 'undefined') item.checked = !!el.checked;
                        } catch(e) {}
                        try {
                            if (typeof el.selectedIndex !== 'undefined') {
                                item.selectedIndex = el.selectedIndex;
                                item.options = coletarOpcoes(el);
                            }
                        } catch(e) {}

                        campos.push(item);
                    }
                }

                return campos;
            }

            function coletarTabelas(doc) {
                var tabelas = [];
                var nodes = [];
                try { nodes = doc.getElementsByTagName('TABLE'); } catch(e) {}
                if (!nodes || !nodes.length) {
                    try { nodes = doc.getElementsByTagName('table'); } catch(e) {}
                }

                for (var i = 0; nodes && i < nodes.length; i++) {
                    var tbl = nodes[i];
                    var tabela = {
                        ordem: i,
                        id: '',
                        name: '',
                        rows: []
                    };
                    try { tabela.id = limpar(tbl.id); } catch(e) {}
                    try { tabela.name = limpar(tbl.name); } catch(e) {}

                    try {
                        for (var r = 0; tbl.rows && r < tbl.rows.length; r++) {
                            var linha = {
                                index: r,
                                cells: []
                            };
                            for (var c = 0; tbl.rows[r].cells && c < tbl.rows[r].cells.length; c++) {
                                linha.cells.push(texto(tbl.rows[r].cells[c]));
                            }
                            tabela.rows.push(linha);
                        }
                    } catch(e) {}

                    tabelas.push(tabela);
                }

                return tabelas;
            }

            function serializarDocumento(win, doc, caminho, profundidade) {
                var item = {
                    caminho: caminho,
                    profundidade: profundidade,
                    name: '',
                    url: '',
                    title: '',
                    bodyText: '',
                    campos: [],
                    tabelas: [],
                    framesFilhos: []
                };

                try { item.name = limpar(win.name); } catch(e) {}
                try { item.url = limpar(doc.location ? doc.location.href : ''); } catch(e) {}
                try { item.title = limpar(doc.title); } catch(e) {}
                try {
                    item.bodyText = limpar(doc.body ? (doc.body.innerText || doc.body.textContent || '') : '');
                } catch(e) {}
                try { item.campos = coletarCampos(doc); } catch(e) {}
                try { item.tabelas = coletarTabelas(doc); } catch(e) {}

                try {
                    for (var i = 0; win.frames && i < win.frames.length; i++) {
                        var child = win.frames[i];
                        item.framesFilhos.push({
                            index: i,
                            name: limpar(child.name || '')
                        });
                    }
                } catch(e) {}

                if (incluirHtml) {
                    try {
                        item.html = String(doc.documentElement ? doc.documentElement.outerHTML || '' : '');
                    } catch(e) {
                        item.html = '';
                    }
                }

                return item;
            }

            var frames = [];
            var visitados = [];

            function jaVisitado(win) {
                for (var i = 0; i < visitados.length; i++) {
                    if (visitados[i] === win) return true;
                }
                return false;
            }

            function visitar(win, caminho, profundidade) {
                if (!win || jaVisitado(win) || profundidade > 10) return;
                visitados.push(win);

                var doc = null;
                try { doc = win.document; } catch(e) {}

                if (doc) {
                    try {
                        frames.push(serializarDocumento(win, doc, caminho, profundidade));
                    } catch(e) {
                        frames.push({
                            caminho: caminho,
                            profundidade: profundidade,
                            erro: String(e.message || e)
                        });
                    }
                }

                try {
                    for (var i = 0; win.frames && i < win.frames.length; i++) {
                        visitar(win.frames[i], caminho + '.frames[' + i + ']', profundidade + 1);
                    }
                } catch(e) {}
            }

            visitar(window, 'window', 0);
            try { if (window.parent && window.parent !== window) visitar(window.parent, 'window.parent', 0); } catch(e) {}
            try { if (window.top && window.top !== window) visitar(window.top, 'window.top', 0); } catch(e) {}

            return {
                ok: true,
                totalFrames: frames.length,
                frames: frames
            };
        """

        try:
            self._garantir_frame_rotina()
            resultado = self.driver.execute_script(script, bool(incluir_html)) or {}
            self._garantir_frame_rotina()
            return resultado if isinstance(resultado, dict) else {"ok": False, "frames": []}
        except Exception as e:
            try:
                self._garantir_frame_rotina()
            except Exception:
                pass
            self.logger.debug(f"03030702 | Falha ao extrair DOM estruturado: {e}")
            return {
                "ok": False,
                "erro": str(e),
                "frames": [],
            }

    def _extrair_campos_chave_do_dom_03030702(self, dom):
        nomes_chave = {
            "mapa",
            "numeroMapa",
            "pontoApoio",
            "SessionID",
            "SubSessionID",
            "opcao",
            "ppopcao",
            "call",
            "produtos",
            "vasilhames",
            "contas",
            "total",
            "totalRetorno",
            "dataEmi",
            "dataDeposito",
            "unidadeMenu",
            "dsUnidadeMenu",
        }
        campos = {}

        for frame in (dom or {}).get("frames") or []:
            caminho = frame.get("caminho", "")
            for campo in frame.get("campos") or []:
                nome = str(campo.get("name") or campo.get("id") or "").strip()
                if nome not in nomes_chave:
                    continue

                valor_campo = str(campo.get("value") or campo.get("text") or "").strip()
                if nome not in campos or valor_campo:
                    campos[nome] = {
                        "value": valor_campo,
                        "frame": caminho,
                        "tag": campo.get("tag", ""),
                        "disabled": campo.get("disabled"),
                    }

        return campos

    def extrair_pagina_json(self, timeout_segundos=20, incluir_html=False):
        """
        Retorna um JSON estruturado com o estado vivo da 03030702.

        A leitura usa o DOM ja renderizado nos iframes, nao o HTML inicial.
        """
        self._garantir_frame_rotina()

        dom = self._extrair_dom_estruturado_03030702(incluir_html=incluir_html)
        campos_chave = self._extrair_campos_chave_do_dom_03030702(dom)
        saida = self.obter_itens_saida(timeout_segundos=timeout_segundos)
        retorno = self.obter_contas_retorno()
        resumo = self.obter_resumo_diferencas()

        try:
            url = self.driver.current_url
        except Exception:
            url = ""

        try:
            titulo = self.driver.title
        except Exception:
            titulo = ""

        mapa = (
            (campos_chave.get("numeroMapa") or {}).get("value")
            or (campos_chave.get("mapa") or {}).get("value")
            or ""
        )
        ponto_apoio = (campos_chave.get("pontoApoio") or {}).get("value") or ""

        return {
            "rotina": "03030702",
            "extraidoEm": datetime.now().isoformat(timespec="seconds"),
            "url": url,
            "titulo": titulo,
            "mapa": mapa,
            "pontoApoio": ponto_apoio,
            "camposChave": campos_chave,
            "resumo": resumo,
            "saida": {
                "itens": saida,
                "totalItens": len(saida),
            },
            "retorno": {
                "linhas": retorno,
                "totalLinhas": len(retorno),
            },
            "dom": dom,
        }

    def equilibrar_contas_saida(self):
        """
        Equilibra Saída x Retorno de forma DINÂMICA.

        Regra principal:
        - Primeiro lê o que JÁ EXISTE no Retorno.
        - Se a categoria já estiver no Retorno, NÃO lança novamente.
        - Isso vale para Vasilhame e para qualquer outra categoria que o
          próprio Promax tenha carregado automaticamente.
        - O MAPA_DE_CONTAS só é usado para descobrir o código de uma
          categoria que realmente está AUSENTE no Retorno.
        - Após cada postback, o Retorno é lido novamente do DOM vivo.

        Vasilhame:
        - Normalmente vem automaticamente no Retorno.
        - Código 0 não é enviado manualmente porque CarregaCondPagto()
          do Promax rejeita código 0.
        - Se Vasilhame estiver na Saída e não existir no Retorno,
          o processo é bloqueado para evitar duplicidade/fechamento incorreto.
        """

        def normalizar_desc(valor):
            return self._normalizar_descricao_conta(valor)

        def normalizar_valor(valor):
            return str(valor or "").strip().replace("R$", "").replace(" ", "")

        def obter_codigo_mapeado(desc_normalizada):
            for chave, cod in self.MAPA_DE_CONTAS:
                if normalizar_desc(chave) in desc_normalizada:
                    return str(cod).strip()
            return None

        def deve_ignorar_saida(desc_normalizada):
            return any(
                conta_ignorada in desc_normalizada
                for conta_ignorada in self.CONTAS_SAIDA_IGNORADAS
            )

        def descricao_equivalente(desc_saida, desc_retorno):
            ds = normalizar_desc(desc_saida)
            dr = normalizar_desc(desc_retorno)

            if not ds or not dr:
                return False

            if ds == dr:
                return True

            if ds in dr or dr in ds:
                return True

            aliases = [
                {"BLOQUETO", "BLOQUETO BANCARIO"},
                {"A VISTA", "DINHEIRO"},
                {"CREDITO CONTA", "CREDITO EM CONTA"},
                {"BONIFICACAO", "BONIFICACAO / VERBA"},
            ]

            for grupo in aliases:
                grupo_norm = {normalizar_desc(x) for x in grupo}
                if ds in grupo_norm and dr in grupo_norm:
                    return True

            return False

        def procurar_no_retorno(item_saida, linhas_retorno, codigo_mapeado=None):
            desc_saida = item_saida.get("descricao", "")
            valor_saida = item_saida.get("valor", "")

            # 1) Se conhecemos o código, ele é o identificador mais forte.
            if codigo_mapeado is not None:
                for linha in linhas_retorno:
                    codigo_retorno = str(
                        linha.get("codigo", "") or ""
                    ).strip()

                    descricao_retorno = str(
                        linha.get("descricao", "") or ""
                    ).strip()

                    if (
                        codigo_retorno
                        and codigo_retorno == str(codigo_mapeado)
                        and descricao_retorno
                        and not linha.get("linhaVazia", False)
                    ):
                        if not self._valores_conta_equivalentes(
                            valor_saida,
                            linha.get("valor", ""),
                        ):
                            return {
                                **linha,
                                "_valor_divergente": True,
                                "_valor_saida": valor_saida,
                            }
                        return linha

            # 2) Depois tenta pela descrição.
            # Isso permite reconhecer inclusive categorias ainda não
            # cadastradas no MAPA_DE_CONTAS quando elas já vierem no Retorno.
            for linha in linhas_retorno:
                if descricao_equivalente(
                    desc_saida,
                    linha.get("descricao", ""),
                ):
                    if not self._valores_conta_equivalentes(
                        valor_saida,
                        linha.get("valor", ""),
                    ):
                        return {
                            **linha,
                            "_valor_divergente": True,
                            "_valor_saida": valor_saida,
                        }
                    return linha

            return None

        # ==========================================================
        # 1. LER A SAÍDA
        # ==========================================================
        itens_saida = self.obter_itens_saida(timeout_segundos=20)

        if not itens_saida:
            raise RuntimeError(
                "Nao foi possivel identificar os itens do iFrameSaida; "
                "o mapa nao sera salvo sem equilibrar as contas."
            )

        self.logger.info(
            f"03030702 | Itens identificados na Saida: {itens_saida}"
        )

        # ==========================================================
        # 2. PROCESSAR ITEM POR ITEM
        # ==========================================================
        for item in itens_saida:

            desc_original = str(
                item.get("descricao", "") or ""
            ).strip()

            desc_normalizada = normalizar_desc(desc_original)
            valor_saida = normalizar_valor(item.get("valor", ""))

            if not desc_original:
                continue

            if deve_ignorar_saida(desc_normalizada):
                self.logger.info(
                    "03030702 | Categoria ignorada na Saida "
                    f"| descricao='{desc_original}' "
                    f"| valor={valor_saida}"
                )
                continue

            # SEMPRE lê o Retorno novamente.
            # Assim qualquer linha automática ou qualquer postback do Promax
            # é considerado antes de decidir lançar.
            linhas_retorno = self.obter_contas_retorno()

            self.logger.info(
                f"03030702 | Validando Saida x Retorno "
                f"| descricao='{desc_original}' "
                f"| valor_saida={valor_saida} "
                f"| retorno_atual={linhas_retorno}"
            )

            codigo_mapeado = obter_codigo_mapeado(
                desc_normalizada
            )

            # ======================================================
            # 3. PRIMEIRO: VER SE JÁ EXISTE NO RETORNO
            # ======================================================
            linha_existente = procurar_no_retorno(
                item_saida=item,
                linhas_retorno=linhas_retorno,
                codigo_mapeado=codigo_mapeado,
            )

            if linha_existente is not None:
                if linha_existente.get("_valor_divergente"):
                    raise RuntimeError(
                        "Conta encontrada no Retorno com valor diferente da Saida. "
                        f"Descricao='{desc_original}' "
                        f"| Valor Saida={linha_existente.get('_valor_saida', valor_saida)} "
                        f"| Valor Retorno={linha_existente.get('valor', '')}"
                    )

                self.logger.info(
                    "03030702 | JA EXISTE NO RETORNO - NAO SERA DUPLICADO "
                    f"| saida='{desc_original}' "
                    f"| valor_saida={valor_saida} "
                    f"| codigo_retorno={linha_existente.get('codigo', '')} "
                    f"| descricao_retorno='{linha_existente.get('descricao', '')}' "
                    f"| valor_retorno={linha_existente.get('valor', '')}"
                )
                continue

            # ======================================================
            # 4. SE NÃO EXISTE, PRECISAMOS SABER O CÓDIGO
            # ======================================================
            if codigo_mapeado is None:
                raise RuntimeError(
                    "Categoria encontrada na Saida, ausente no Retorno e "
                    "sem codigo mapeado. O mapa nao sera salvo. "
                    f"Descricao='{desc_original}' | Valor={valor_saida}"
                )

            # ======================================================
            # 5. VASILHAME / CÓDIGO 0 É AUTOMÁTICO
            # ======================================================
            if codigo_mapeado == "0":
                raise RuntimeError(
                    "Vasilhame foi encontrado na Saida, mas nao foi localizado "
                    "no Retorno automatico do Promax. Como codigo 0 nao pode ser "
                    "lancado manualmente por CarregaCondPagto(), o mapa foi "
                    "bloqueado para evitar fechamento incorreto. "
                    f"Valor da Saida={valor_saida}"
                )

            if not valor_saida or valor_saida in (
                "0", "0,00", "0.00"
            ):
                self.logger.info(
                    "03030702 | Categoria ausente do Retorno, mas sem valor "
                    f"a lancar | codigo={codigo_mapeado} "
                    f"| descricao='{desc_original}' "
                    f"| valor={valor_saida}"
                )
                continue

            # ======================================================
            # 6. LANÇAR SOMENTE O QUE REALMENTE ESTÁ FALTANDO
            # ======================================================
            self.logger.info(
                "03030702 | AUSENTE NO RETORNO - LANCANDO "
                f"| codigo={codigo_mapeado} "
                f"| descricao='{desc_original}' "
                f"| valor={valor_saida}"
            )

            sucesso = self.lancar_conta_retorno(
                codigo_conta=codigo_mapeado,
                valor=valor_saida,
            )

            if not sucesso:
                raise RuntimeError(
                    f"Falha ao preencher conta {codigo_mapeado} "
                    f"({desc_original}) com valor {valor_saida}."
                )

            # ======================================================
            # 7. VALIDAR DEPOIS DO POSTBACK
            # ======================================================
            linhas_pos = self.obter_contas_retorno()

            linha_confirmada = procurar_no_retorno(
                item_saida=item,
                linhas_retorno=linhas_pos,
                codigo_mapeado=codigo_mapeado,
            )

            if linha_confirmada is None:
                raise RuntimeError(
                    "O Promax executou o lancamento, mas a conta nao foi "
                    "encontrada no Retorno apos o postback. "
                    f"Codigo={codigo_mapeado} "
                    f"| Descricao='{desc_original}'"
                )

            if linha_confirmada.get("_valor_divergente"):
                raise RuntimeError(
                    "O Promax executou o lancamento, mas confirmou valor diferente "
                    "do valor da Saida. "
                    f"Codigo={codigo_mapeado} "
                    f"| Descricao='{desc_original}' "
                    f"| Valor Saida={linha_confirmada.get('_valor_saida', valor_saida)} "
                    f"| Valor Retorno={linha_confirmada.get('valor', '')}"
                )

            self.logger.info(
                "03030702 | LANCAMENTO CONFIRMADO NO RETORNO "
                f"| codigo={linha_confirmada.get('codigo', '')} "
                f"| descricao='{linha_confirmada.get('descricao', '')}' "
                f"| valor_retorno={linha_confirmada.get('valor', '')}"
            )

        # ==========================================================
        # 8. VALIDAÇÃO FINAL
        # ==========================================================
        linhas_finais = self.obter_contas_retorno()

        pendencias = []

        for item in itens_saida:
            desc_original = str(
                item.get("descricao", "") or ""
            ).strip()

            if not desc_original:
                continue

            desc_normalizada = normalizar_desc(desc_original)
            if deve_ignorar_saida(desc_normalizada):
                continue

            if not self._diferenca_tem_valor(item.get("valor", "")):
                continue

            codigo_mapeado = obter_codigo_mapeado(desc_normalizada)

            existente = procurar_no_retorno(
                item_saida=item,
                linhas_retorno=linhas_finais,
                codigo_mapeado=codigo_mapeado,
            )

            if existente is None or existente.get("_valor_divergente"):
                pendencias.append({
                    "descricao": desc_original,
                    "valor": item.get("valor", ""),
                    "codigo": codigo_mapeado,
                    "valor_retorno": (existente or {}).get("valor", ""),
                })

        if pendencias:
            raise RuntimeError(
                "Ainda existem categorias da Saida ausentes no Retorno. "
                f"Pendencias={pendencias}"
            )

        self.logger.info(
            "03030702 | VALIDACAO FINAL OK: todas as categorias da Saida "
            "ja existiam ou foram lancadas no Retorno."
        )

        # ==========================================================
        # 9. RECALCULAR TOTAL PELO PRÓPRIO PROMAX
        # ==========================================================
        try:
            if self._entrar_iframe_retorno_nativo():
                calculo = self.driver.execute_script(
                    """
                    try {
                        if (typeof CalculaTotal === 'function') {
                            CalculaTotal();
                            return {
                                ok: true,
                                totalRetorno: document.all.totalRetorno
                                    ? document.all.totalRetorno.value
                                    : ''
                            };
                        }
                    } catch(e) {
                        return {
                            ok: false,
                            erro: String(e.message || e)
                        };
                    }

                    return {
                        ok: false,
                        erro: 'CalculaTotal nao localizada'
                    };
                    """
                )

                self.logger.info(
                    f"03030702 | Recalculo final do Retorno: {calculo}"
                )
        finally:
            self._garantir_frame_rotina()

        self._adicionar_linha_vazia_retorno()

        resumo = self.obter_resumo_diferencas()

        self.logger.info(
            f"03030702 | Diferencas apos equilibrio: {resumo}"
        )

    def salvar_mapa(self):
        """
        Salva o mapa e só considera sucesso quando o Promax devolver
        um alerta explícito de liberação/sucesso/fechamento.
        """
        try:
            self._garantir_frame_rotina()
            self.logger.info(
                "03030702 | Verificando diferencas antes de salvar..."
            )

            resumo_previo = self.obter_resumo_diferencas()
            tot_diferenca = str(resumo_previo.get("total", "") or "").strip()
            contas_diferenca = str(resumo_previo.get("contas", "") or "").strip()

            if self._diferenca_tem_valor(tot_diferenca) or self._diferenca_tem_valor(
                contas_diferenca
            ):
                self.logger.info(
                    "03030702 | Diferencas detectadas antes do salvamento "
                    f"| Total={tot_diferenca} | Contas={contas_diferenca}. "
                    "Executando equilibrio novamente."
                )
                self.equilibrar_contas_saida()

                resumo_pos = self.obter_resumo_diferencas()
                self.logger.info(
                    f"03030702 | Diferencas imediatamente antes do Salvar(): {resumo_pos}"
                )
                total_pos = str(resumo_pos.get("total", "") or "").strip()
                contas_pos = str(resumo_pos.get("contas", "") or "").strip()
                if self._diferenca_tem_valor(total_pos) or self._diferenca_tem_valor(
                    contas_pos
                ):
                    return ExecutionResult(
                        status=ExecutionStatus.BUSINESS_FAILURE,
                        message=(
                            "Mapa nao salvo: ainda existem diferencas apos "
                            "reequilibrar a prestacao de contas."
                        ),
                        metadata={
                            "integration_code": "DIFERENCA_PRESTACAO_CONTAS",
                            "resumo": resumo_pos,
                        },
                    )

            self.logger.info(
                "03030702 | Executando Salvar() e aguardando alerta do Promax..."
            )

            self._instalar_interceptador_alertas_salvar()
            self._garantir_frame_rotina()

            script_salvar = self.JS_RECURSIVE_FRAME_FINDER + """
                var r = getRotinaWin();

                if (r && typeof r.Salvar === 'function') {
                    r.Salvar();
                    return true;
                }

                if (r && r.document) {
                    var b = r.document.getElementsByName('BotSalvar')[0];
                    if (b) {
                        b.click();
                        return true;
                    }
                }

                try {
                    var b2 = document.getElementsByName('BotSalvar')[0];
                    if (b2) {
                        b2.click();
                        return true;
                    }
                } catch(e) {}

                return false;
            """

            disparou = self.driver.execute_script(script_salvar)

            if disparou is False:
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message="Nao foi possivel disparar o Salvar() da rotina 03030702.",
                )

            # O alerta é a confirmação da operação. Aguarda por até 12 segundos.
            fim = time.time() + 12
            alerta_texto = None

            while time.time() < fim:
                alerta_texto = self._lidar_com_alerta_ie()
                if alerta_texto:
                    break
                time.sleep(0.25)

            if alerta_texto:
                texto_lower = alerta_texto.lower()

                if (
                    "liberad" in texto_lower
                    or "sucesso" in texto_lower
                    or "fechado" in texto_lower
                    or "prestacao de contas sera executado" in texto_lower
                    or "prestacao de contas sera executada" in texto_lower
                    or "prestação de contas será executado" in texto_lower
                    or "prestação de contas será executada" in texto_lower
                ):
                    self.logger.info(
                        f"03030702 | Sucesso confirmado pelo Promax: {alerta_texto}"
                    )
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        message=f"Mapa salvo e processado: {alerta_texto}",
                        metadata={
                            "integration_code": "MAPA_LIBERADO_FINANCEIRO",
                            "alerta": alerta_texto,
                        },
                    )

                self.logger.warning(
                    f"03030702 | Alerta de negocio ao salvar: {alerta_texto}"
                )
                return ExecutionResult(
                    status=ExecutionStatus.BUSINESS_FAILURE,
                    message=f"Alerta do sistema ao salvar: {alerta_texto}",
                    metadata={"alerta": alerta_texto},
                )

            # Sem alerta, não confirma sucesso.
            self.logger.warning(
                "03030702 | Salvar() foi executado, mas nenhum alerta de confirmacao "
                "foi recebido dentro do tempo esperado."
            )
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=(
                    "Salvar() executado, mas o Promax nao retornou alerta de "
                    "confirmacao da liberacao do mapa."
                ),
            )

        except Exception as e:
            self.logger.error(
                f"03030702 | Erro inesperado ao salvar mapa: {e}"
            )
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao salvar mapa: {str(e)}",
            )

    def abrir_pix(self):
        """Clica no botao PIX 100% via JS."""
        self._garantir_frame_rotina()
        script = self.JS_RECURSIVE_FRAME_FINDER + "var r = getRotinaWin(); if (r && typeof r.Pix === 'function') r.Pix();"
        self.driver.execute_script(script)

    def abrir_pgd(self):
        """Clica no botao PGD 100% via JS."""
        self._garantir_frame_rotina()
        script = self.JS_RECURSIVE_FRAME_FINDER + "var r = getRotinaWin(); if (r && typeof r.Pgd === 'function') r.Pgd();"
        self.driver.execute_script(script)

    def abrir_recibos(self):
        """Clica no botao Recibos 100% via JS."""
        self._garantir_frame_rotina()
        script = self.JS_RECURSIVE_FRAME_FINDER + "var r = getRotinaWin(); if (r && typeof r.Recibos === 'function') r.Recibos();"
        self.driver.execute_script(script)

    def cancelar(self):
        """Clica no botao Cancelar 100% via JS."""
        self._garantir_frame_rotina()
        script = self.JS_RECURSIVE_FRAME_FINDER + "var r = getRotinaWin(); if (r && typeof r.Cancelar === 'function') r.Cancelar();"
        self.driver.execute_script(script)
