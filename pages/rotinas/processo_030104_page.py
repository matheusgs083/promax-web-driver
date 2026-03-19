import os
import csv
import pandas as pd
import datetime as dt
import time
from pages.rotina_page import RotinaPage

class Processo030104Page(RotinaPage):
    FRAME_ROTINA = 1

    # --- MÉTODO DE LEITURA (ESTÁTICO/OFFLINE) ---
    def ler_planilha_pedidos(self, caminho_planilha):
        """Lê o Excel e agrupa itens por pedido (Cabeçalho) com tratamento de tipos."""
        self.logger.info(f"Iniciando leitura da planilha: {caminho_planilha}")
        
        try:
            # dtype=str garante que códigos com zeros à esquerda não sejam convertidos para int
            df = pd.read_excel(caminho_planilha, dtype=str)
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            colunas_cabecalho = ['mapa', 'vendedor', 'operacao', 'cliente']
            
            # Validação básica de colunas
            if not set(colunas_cabecalho).issubset(df.columns):
                raise ValueError(f"Colunas obrigatórias ausentes: {colunas_cabecalho}")

            # Preenche células mescladas do Excel (comum em relatórios de pedidos)
            df[colunas_cabecalho] = df[colunas_cabecalho].ffill()
            df = df.dropna(subset=['item']) 

            pedidos_agrupados = []
            
            # Agrupamento por dados únicos de cabeçalho
            for chaves, grupo in df.groupby(colunas_cabecalho, dropna=False):
                itens = []
                for _, row in grupo.iterrows():
                    # Formatação de TTV (Troca . por , para o input do sistema)
                    ttv_raw = str(row.get('ttv', '')).strip()
                    ttv_val = ttv_raw.replace('.', ',') if ttv_raw and ttv_raw != 'nan' else None
                    
                    itens.append({
                        'codigo': str(row['item']).strip().split('.')[0], 
                        'qtd': str(row['quantidade']).strip().split('.')[0],
                        'ttv': ttv_val
                    })
                    
                pedidos_agrupados.append({
                    'mapa': str(chaves[0]).split('.')[0] if chaves[0] not in ['0', None] else '0',
                    'vendedor': str(chaves[1]).split('.')[0],
                    'operacao': str(chaves[2]).split('.')[0],
                    'cliente': str(chaves[3]).split('.')[0],
                    'itens': itens
                })
                
            self.logger.info(f"Sucesso: {len(pedidos_agrupados)} pedidos agrupados.")
            return pedidos_agrupados

        except Exception as e:
            self.logger.error(f"Erro ao processar planilha: {str(e)}")
            return []

    # --- MÉTODOS DE AUTOMAÇÃO ---
    def digitar_pedido_completo(self, dados_pedido, caminho_log_csv):
        """Executa a inserção completa de um pedido no sistema."""
        self.entrar_frame_rotina_blindado(self.FRAME_ROTINA)
        
        # Bypass em modais de confirmação nativos do navegador
        self.driver.execute_script("window.msgbxSimNao = function(t, m, fSim, fNao){ fSim(); };")

        mapa = str(dados_pedido['mapa']).strip()
        cliente = str(dados_pedido['cliente']).strip()

        # 1. CABEÇALHO
        # Carrega o Mapa (gatilho 2 é o padrão Promax para busca)
        ok_mapa, msg_mapa = self.preencher_campo_com_gatilho("nrMapa", mapa, "CarregaMapa(2);")
        if not ok_mapa:
            return False, f"Mapa {mapa} inválido ou não carregado: {msg_mapa}"
        
        self._fechar_aba_mpd_se_aberta()

        # Preenchimento sequencial de vendedores e destinatários
        campos_head = [
            ("cdVendedor", dados_pedido['vendedor'], "CarregaVendedor();"),
            ("cdOperacao", dados_pedido['operacao'], "CarregaOperacao();"),
            ("cdDestinatario", cliente, "CarregaCliente();")
        ]
        
        for campo, val, trigger in campos_head:
            ok, msg = self.preencher_campo_com_gatilho(campo, val, trigger)
            if not ok: 
                self.executar_gatilho_e_aguardar("Cancelar();")
                return False, f"Erro no cabeçalho ({campo}): {msg}"

        # 2. INSERÇÃO DE ITENS
        sucessos = 0
        colunas_log = ['data_hora', 'mapa', 'cliente', 'produto', 'quantidade', 'status', 'motivo']
        
        for item in dados_pedido['itens']:
            ok_item, motivo = self._processar_item(item)
            
            # Registro de Log por Item
            self.registrar_log_csv(caminho_log_csv, colunas_log, {
                'data_hora': dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                'mapa': mapa, 
                'cliente': cliente, 
                'produto': item['codigo'],
                'quantidade': item['qtd'], 
                'status': "SUCESSO" if ok_item else "FALHA", 
                'motivo': motivo
            })
            
            if ok_item: 
                sucessos += 1

        # 3. FINALIZAÇÃO DO PEDIDO
        if sucessos == 0:
            self.executar_gatilho_e_aguardar("Cancelar();")
            return False, "Pedido abortado: Nenhum item foi aceito pelo sistema."

        # Salva o pedido consolidado
        salvou, msg_final = self.executar_gatilho_e_aguardar("Salvar();")
        return salvou, msg_final

    def _processar_item(self, item):
        """Lógica de baixo nível para preencher a grade de produtos."""
        try:
            self.driver.execute_script("NovoItem();")
            
            # Injeção direta de valores para rapidez e evitar erros de foco
            self.js_set_input_by_name('codProduto', item['codigo'])
            self.js_set_input_by_name('qtPedida', item['qtd'])
            
            if item.get('ttv'):
                self.js_set_input_by_name('valorTTV', item['ttv'])
            
            # Gatilho de adição (Simula o clique no disquete azul)
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
        Tratamento para o modal de 'Motivo de Não Carga' que aparece 
        quando um cliente possui restrições de logística.
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
                time.sleep(1.2) # Aguarda animação de fechamento do modal
                self.logger.info("Modal MPD detectado e fechado automaticamente.")
        except:
            pass