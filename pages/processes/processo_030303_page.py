import time
import unicodedata

from core.execution.execution_result import ExecutionResult, ExecutionStatus
from pages.common.rotina_page import RotinaPage


class Processo030303Page(RotinaPage):
    """Processo 030303: Manutenção/Alocação de Equipe no Mapa (PW02103C)."""

    FRAME_ROTINA = 1

    def __init__(self, driver, handle_menu_original):
        super().__init__(driver, handle_menu_original)
        try:
            self.handle_rotina = self.driver.current_window_handle
        except Exception:
            self.handle_rotina = None

    @staticmethod
    def normalizar_mapa(mapa):
        valor = str(mapa or "").strip()
        if valor.endswith(".0"):
            valor = valor[:-2]
        valor = valor.replace(".", "").replace(",", "")
        if not valor or valor == "0":
            raise ValueError("Mapa deve ser informado e diferente de zero.")
        if not valor.isdigit():
            raise ValueError(f"Mapa invalido: {mapa}")
        return valor

    @staticmethod
    def _normalizar_texto(texto):
        texto = str(texto or "").lower()
        texto = unicodedata.normalize("NFKD", texto)
        return "".join(char for char in texto if not unicodedata.combining(char))

    @staticmethod
    def _valor_campo_extraido(campo):
        valor = (campo or {}).get("value")
        if isinstance(valor, dict):
            valor = valor.get("texto") or valor.get("valor")
        return str(valor or "").strip()

    @classmethod
    def _campo_extraido_por_nome(cls, dados, nome):
        nome_norm = cls._normalizar_texto(nome)
        candidatos = []
        for campo in (dados or {}).get("campos") or []:
            nomes = (
                campo.get("name"),
                campo.get("id"),
                campo.get("label"),
            )
            if any(cls._normalizar_texto(item) == nome_norm for item in nomes if item):
                valor = cls._valor_campo_extraido(campo)
                if valor:
                    candidatos.append(valor)
        for valor in reversed(candidatos):
            texto = cls._normalizar_texto(cls._limpar_nome_com_codigo(valor))
            if texto and "selecionar" not in texto and texto not in {"00000"}:
                return valor
        return candidatos[-1] if candidatos else ""

    @staticmethod
    def _limpar_nome_com_codigo(valor):
        texto = str(valor or "").strip()
        if " - " in texto:
            texto = texto.split(" - ", 1)[1].strip()
        return texto.replace("(*)", "").strip()

    @classmethod
    def _dados_equipe_validos(cls, dados):
        if not isinstance(dados, dict):
            return False
        motorista = cls._campo_extraido_por_nome(dados, "Motorista") or cls._campo_extraido_por_nome(dados, "csMotorista") or cls._campo_extraido_por_nome(dados, "cdMotorista")
        placa = cls._campo_extraido_por_nome(dados, "Placa") or cls._campo_extraido_por_nome(dados, "Veiculo")
        nome_motorista = cls._normalizar_texto(cls._limpar_nome_com_codigo(motorista))
        placa_norm = cls._normalizar_texto(placa)
        return bool(
            nome_motorista
            and "selecionar" not in nome_motorista
            and "pau brasil" not in nome_motorista
            and placa_norm
            and "selecionar" not in placa_norm
        )

    def _aguardar_dados_equipe_carregados(self, timeout=6):
        fim = time.time() + max(float(timeout or 0), 0)
        ultimo = {}
        while time.time() <= fim:
            ultimo = self.extrair_pagina_json()
            if self._dados_equipe_validos(ultimo):
                return ultimo
            time.sleep(0.5)
        return ultimo

    @classmethod
    def _enriquecer_motorista(cls, dados):
        if not isinstance(dados, dict):
            return dados

        motorista_original = cls._campo_extraido_por_nome(dados, "Motorista")
        origem_nome = "Motorista"
        if not motorista_original:
            motorista_original = cls._campo_extraido_por_nome(dados, "csMotorista")
            origem_nome = "csMotorista"
        if not motorista_original:
            motorista_original = cls._campo_extraido_por_nome(dados, "cdMotorista")
            origem_nome = "cdMotorista"

        nome_motorista = cls._limpar_nome_com_codigo(motorista_original)
        if "pau brasil" in cls._normalizar_texto(nome_motorista):
            ajudante = cls._campo_extraido_por_nome(dados, "Ajudante 1") or cls._campo_extraido_por_nome(dados, "ajudante1")
            if ajudante:
                motorista_original = ajudante
                nome_motorista = cls._limpar_nome_com_codigo(ajudante)
                origem_nome = "ajudante1"

        motorista = dados.get("motorista") if isinstance(dados.get("motorista"), dict) else {}
        dados["motorista"] = {
            **motorista,
            "nome": nome_motorista,
            "origem_nome": origem_nome,
            "valor_original": motorista_original,
        }
        return dados

    def _logar_dados_equipe(self, dados, contexto):
        try:
            self.logger.info(
                "030303 | Dados equipe capturados (%s): motorista=%s | origem=%s | placa=%s | ajudante1=%s | ajudante2=%s",
                contexto,
                ((dados or {}).get("motorista") or {}).get("nome"),
                ((dados or {}).get("motorista") or {}).get("origem_nome"),
                self._campo_extraido_por_nome(dados, "Placa") or self._campo_extraido_por_nome(dados, "Veiculo"),
                self._campo_extraido_por_nome(dados, "Ajudante 1") or self._campo_extraido_por_nome(dados, "ajudante1"),
                self._campo_extraido_por_nome(dados, "Ajudante 2") or self._campo_extraido_por_nome(dados, "ajudante2"),
            )
        except Exception:
            pass

    def carregar_mapa(self, mapa):
        """Preenche e carrega o mapa na rotina 030303 via gatilho CarregarMapa()."""
        mapa_norm = self.normalizar_mapa(mapa)
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            self.logger.info(f"030303 | Carregando mapa: {mapa_norm}")

            ok, msg = self.preencher_campo_com_gatilho("mapa", mapa_norm, "CarregarMapa();")

            alertas = self.lidar_com_alertas(tentativas=2, timeout=2)
            if alertas:
                for alerta in alertas:
                    msg_alerta = str(alerta).strip()
                    msg_norm = self._normalizar_texto(msg_alerta)
                    if any(
                        kw in msg_norm
                        for kw in ["erro", "invalido", "nao encontrado", "nao existe", "bloquead"]
                    ):
                        return ExecutionResult(
                            status=ExecutionStatus.BUSINESS_FAILURE,
                            message=f"Alerta ao carregar mapa {mapa_norm}: {msg_alerta}",
                        )

            if not ok and "timeout" in str(msg).lower():
                return ExecutionResult(
                    status=ExecutionStatus.TECHNICAL_FAILURE,
                    message=f"Timeout ao carregar mapa {mapa_norm}: {msg}",
                )

            dados_030303 = self._aguardar_dados_equipe_carregados()
            self._logar_dados_equipe(dados_030303, "carregar")

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Mapa {mapa_norm} carregado com sucesso na 030303.",
                metadata={
                    "mapa": mapa_norm,
                    "dados_030303": dados_030303,
                },
            )
        except Exception as e:
            self.logger.error(f"030303 | Erro ao carregar mapa {mapa_norm}: {e}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Falha ao carregar mapa {mapa_norm}: {str(e)}",
            )

    def extrair_pagina_json(self):
        """Extrai dados estruturados da 030303, incluindo campos de motorista quando existirem."""
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            dados = self.driver.execute_script(
                """
                function texto(el) {
                    if (!el) return "";
                    return String(el.innerText || el.textContent || el.value || "").replace(/\\s+/g, " ").replace(/^\\s+|\\s+$/g, "");
                }
                function valor(el) {
                    if (!el) return "";
                    var tag = String(el.tagName || "").toLowerCase();
                    if (tag === "select") {
                        var opt = el.options && el.selectedIndex >= 0 ? el.options[el.selectedIndex] : null;
                        return {
                            valor: String(el.value || "").replace(/^\\s+|\\s+$/g, ""),
                            texto: texto(opt)
                        };
                    }
                    return String(el.value || texto(el) || "").replace(/^\\s+|\\s+$/g, "");
                }
                function encontrarLabelPorFor(id) {
                    if (!id) return null;
                    var labels = document.getElementsByTagName('label');
                    for (var i = 0; i < labels.length; i++) {
                        if (String(labels[i].htmlFor || labels[i].getAttribute('for') || '') === String(id)) {
                            return labels[i];
                        }
                    }
                    return null;
                }
                function labelProximo(el) {
                    var id = el && el.id;
                    if (id) {
                        var lab = encontrarLabelPorFor(id);
                        if (lab) return texto(lab);
                    }
                    function textoFilhosSemCampo(node) {
                        if (!node) return "";
                        var clone = node.cloneNode(true);
                        var tagsCampo = ['input', 'select', 'textarea', 'button'];
                        for (var tci = 0; tci < tagsCampo.length; tci++) {
                            var campos = clone.getElementsByTagName(tagsCampo[tci]);
                            while (campos && campos.length) {
                                if (campos[0] && campos[0].parentNode) campos[0].parentNode.removeChild(campos[0]);
                                else break;
                            }
                        }
                        return texto(clone);
                    }
                    var atual = el;
                    for (var i = 0; atual && i < 4; i++) {
                        var prev = atual.previousElementSibling;
                        if (prev) {
                            var t = textoFilhosSemCampo(prev);
                            if (t) return t;
                        }
                        if (atual.parentElement) {
                            var siblings = atual.parentElement.children || [];
                            for (var si = 0; si < siblings.length; si++) {
                                if (siblings[si] === atual) break;
                                var st = textoFilhosSemCampo(siblings[si]);
                                if (st) return st;
                            }
                        }
                        atual = atual.parentElement;
                    }
                    return "";
                }

                var campos = [];
                var motorista = {};
                var els = [];
                var tags = ['input', 'select', 'textarea'];
                for (var ti = 0; ti < tags.length; ti++) {
                    var encontrados = document.getElementsByTagName(tags[ti]);
                    for (var ei = 0; ei < encontrados.length; ei++) {
                        els.push(encontrados[ei]);
                    }
                }
                for (var ix = 0; ix < els.length; ix++) {
                    var el = els[ix];
                    var v = valor(el);
                    var valorCampo = (typeof v === "object") ? (v.texto || v.valor) : v;
                    if (!valorCampo) continue;
                    var chave = String(el.name || el.id || labelProximo(el) || "").replace(/^\\s+|\\s+$/g, "");
                    var item = {
                        name: el.name || "",
                        id: el.id || "",
                        label: labelProximo(el),
                        value: v
                    };
                    campos.push(item);
                    var alvo = (chave + " " + item.label + " " + valorCampo).toLowerCase();
                    if (alvo.indexOf("motor") >= 0 || alvo.indexOf("mot") >= 0) {
                        motorista[chave || item.label || item.id || item.name || "motorista"] = valorCampo;
                    }
                }
                function normalizar(s) {
                    return String(s || "").toLowerCase()
                        .replace(/[áàãâä]/g, "a")
                        .replace(/[éèêë]/g, "e")
                        .replace(/[íìîï]/g, "i")
                        .replace(/[óòõôö]/g, "o")
                        .replace(/[úùûü]/g, "u")
                        .replace(/[ç]/g, "c")
                        .replace(/\\s+/g, " ").replace(/^\\s+|\\s+$/g, "");
                }
                function campoVisivel(el) {
                    if (!el) return false;
                    var r = el.getBoundingClientRect();
                    return r && r.width > 0 && r.height > 0;
                }
                function encontrarCampoPorRotulo(rotulo) {
                    var alvo = normalizar(rotulo);
                    var todosEncontrados = document.getElementsByTagName("*");
                    var todos = [];
                    for (var tidx = 0; tidx < todosEncontrados.length; tidx++) {
                        todos.push(todosEncontrados[tidx]);
                    }
                    var labels = [];
                    for (var li = 0; li < todos.length; li++) {
                        var itemTexto = normalizar(todos[li].innerText || todos[li].textContent || "");
                        if (itemTexto === alvo && campoVisivel(todos[li])) labels.push(todos[li]);
                    }
                    var controles = [];
                    var tagsControle = ["input", "select", "textarea"];
                    for (var tagCtrlIdx = 0; tagCtrlIdx < tagsControle.length; tagCtrlIdx++) {
                        var controlesEncontrados = document.getElementsByTagName(tagsControle[tagCtrlIdx]);
                        for (var ctrlIdx = 0; ctrlIdx < controlesEncontrados.length; ctrlIdx++) {
                            if (campoVisivel(controlesEncontrados[ctrlIdx])) {
                                controles.push(controlesEncontrados[ctrlIdx]);
                            }
                        }
                    }
                    for (var lidx = 0; lidx < labels.length; lidx++) {
                        var lr = labels[lidx].getBoundingClientRect();
                        var melhor = null;
                        var melhorScore = 999999;
                        for (var cidx = 0; cidx < controles.length; cidx++) {
                            var cr = controles[cidx].getBoundingClientRect();
                            if (cr.left + 4 < lr.right) continue;
                            if (Math.abs(cr.top - lr.top) > 90) continue;
                            var score = Math.abs(cr.top - lr.top) * 20 + Math.max(0, cr.left - lr.right);
                            if (score < melhorScore) {
                                melhorScore = score;
                                melhor = controles[cidx];
                            }
                        }
                        if (melhor) return melhor;
                    }
                    return null;
                }
                var rotulosEquipe = ["Veiculo", "Placa", "Motorista", "Ajudante 1", "Ajudante 2"];
                for (var ridx = 0; ridx < rotulosEquipe.length; ridx++) {
                    var rotulo = rotulosEquipe[ridx];
                    var controle = encontrarCampoPorRotulo(rotulo);
                    if (!controle) continue;
                    var v = valor(controle);
                    var valorCampo = (typeof v === "object") ? (v.texto || v.valor) : v;
                    if (!valorCampo) continue;
                    campos.push({
                        name: controle.name || "",
                        id: controle.id || "",
                        label: rotulo,
                        value: v,
                        origem: "rotulo-visual"
                    });
                    if (rotulo === "Motorista") motorista[rotulo] = valorCampo;
                }
                return {
                    rotina: "030303",
                    campos: campos,
                    motorista: motorista
                };
                """
            )
            if isinstance(dados, dict):
                return self._enriquecer_motorista(dados)
            return {"rotina": "030303", "valor": dados}
        except Exception as e:
            if hasattr(self.logger, "warning"):
                self.logger.warning(f"030303 | Nao foi possivel extrair dados estruturados: {e}")
            return {
                "rotina": "030303",
                "erro": str(e),
            }

    def salvar_mapa(self):
        """Executa a acao de salvar (Salvar();) na rotina 030303."""
        try:
            self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
            self.logger.info("030303 | Salvando mapa...")

            salvou, msg = self.executar_gatilho_e_aguardar("Salvar();")

            alertas = self.lidar_com_alertas(tentativas=2, timeout=2)
            msg_final = msg
            if alertas:
                msg_final = " | ".join(str(a) for a in alertas)

            if not salvou:
                status = (
                    ExecutionStatus.TECHNICAL_FAILURE
                    if "timeout" in str(msg_final).lower()
                    else ExecutionStatus.BUSINESS_FAILURE
                )
                return ExecutionResult(
                    status=status,
                    message=f"Falha ao salvar mapa na 030303: {msg_final}",
                )

            dados_030303 = self._aguardar_dados_equipe_carregados(timeout=3)
            self._logar_dados_equipe(dados_030303, "salvar")

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Mapa salvo com sucesso na rotina 030303. {msg_final}".strip(),
                metadata={
                    "dados_030303": dados_030303,
                },
            )
        except Exception as e:
            self.logger.error(f"030303 | Erro tecnico ao salvar mapa: {e}")
            return ExecutionResult(
                status=ExecutionStatus.TECHNICAL_FAILURE,
                message=f"Erro ao salvar mapa na 030303: {str(e)}",
            )
