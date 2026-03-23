import csv
import os
import time
from datetime import datetime

class RelatorioExecucao:
    def __init__(self):
        self.registros = []
        self.inicio_total = time.time() 

    def anotar(self, rotina, unidade, status, detalhe, duracao_segundos=0):
        """Registra o resultado e o tempo de uma unidade na memória."""
        minutos, segundos = divmod(int(duracao_segundos), 60)
        duracao_formatada = f"{minutos:02d}:{segundos:02d}"

        self.registros.append({
            "Hora": datetime.now().strftime("%H:%M:%S"),
            "Rotina": rotina,
            "Unidade": unidade,
            "Status": status,
            "Duração": duracao_formatada,
            "duracao_raw": int(duracao_segundos),
            "Detalhes": detalhe
        })

    def gerar_csv(self, diretorio_destino):
        """Gera logs diários sem nunca apagar os antigos."""
        if not self.registros:
            return None
            
        os.makedirs(diretorio_destino, exist_ok=True)
        
        # Nome baseado apenas na DATA para agrupar execuções do mesmo dia
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        
        caminho_detalhado = os.path.join(diretorio_destino, f"Log_Detalhado_{data_hoje}.csv")
        caminho_resumido = os.path.join(diretorio_destino, f"Log_Resumido_{data_hoje}.csv")
        
        tempo_total_segundos = time.time() - self.inicio_total
        horas_t, resto_t = divmod(int(tempo_total_segundos), 3600)
        min_t, seg_t = divmod(resto_t, 60)
        tempo_robo_formatado = f"{horas_t:02d}:{min_t:02d}:{seg_t:02d}"

        # ==========================================================
        # 1. LOG DETALHADO (Modo 'a' para anexar/Append)
        # ==========================================================
        existe_detalhe = os.path.exists(caminho_detalhado)
        with open(caminho_detalhado, mode='a', newline='', encoding='utf-8-sig') as arq_detalhe:
            chaves_csv = ["Hora", "Rotina", "Unidade", "Status", "Duração", "Detalhes"]
            writer = csv.DictWriter(arq_detalhe, fieldnames=chaves_csv, delimiter=';', extrasaction='ignore')
            
            if not existe_detalhe:
                writer.writeheader()
            
            writer.writerows(self.registros)
            # Linha separadora para identificar o fim de uma execução específica
            writer.writerow({"Hora": "---", "Rotina": f"FIM EXECUÇÃO {datetime.now().strftime('%H:%M')}", "Status": "TEMPO TOTAL", "Duração": tempo_robo_formatado})

        # ==========================================================
        # 2. LOG RESUMIDO (Modo 'a' para anexar/Append)
        # ==========================================================
        agrupamento = {}
        for r in self.registros:
            rotina = r["Rotina"]
            if rotina not in agrupamento:
                agrupamento[rotina] = {
                    "Hora Início": r["Hora"],
                    "Qtd Sucesso": 0,
                    "Qtd Falha": 0,
                    "Erros": [],
                    "Tempo Total": 0
                }
            agrupamento[rotina]["Tempo Total"] += r.get("duracao_raw", 0)
            if r["Status"] == "SUCESSO":
                agrupamento[rotina]["Qtd Sucesso"] += 1
            else:
                agrupamento[rotina]["Qtd Falha"] += 1
                agrupamento[rotina]["Erros"].append(f"Filial {r['Unidade']}: {r['Detalhes']}")
        
        linhas_resumo = []
        for rotina, dados in agrupamento.items():
            minutos, segundos = divmod(dados["Tempo Total"], 60)
            total_unidades = dados["Qtd Sucesso"] + dados["Qtd Falha"]
            status_geral = "SUCESSO" if dados["Qtd Falha"] == 0 else "COM ERROS"
            detalhes = f"OK ({total_unidades} filiais)" if dados["Qtd Falha"] == 0 else f"{dados['Qtd Falha']} falha(s). Erros: " + " | ".join(dados["Erros"])

            linhas_resumo.append({
                "Hora Início": dados["Hora Início"],
                "Rotina": rotina,
                "Status": status_geral,
                "Tempo Total": f"{minutos:02d}:{segundos:02d}",
                "Detalhes": detalhes
            })
        
        existe_resumo = os.path.exists(caminho_resumido)
        with open(caminho_resumido, mode='a', newline='', encoding='utf-8-sig') as arq_resumo:
            chaves_resumo = ["Hora Início", "Rotina", "Status", "Tempo Total", "Detalhes"]
            writer = csv.DictWriter(arq_resumo, fieldnames=chaves_resumo, delimiter=';')
            
            if not existe_resumo:
                writer.writeheader()
            
            writer.writerows(linhas_resumo)
            writer.writerow({"Rotina": "FINALIZADO", "Tempo Total": tempo_robo_formatado})

        return f"\n -> {caminho_detalhado}\n -> {caminho_resumido}"

tracker = RelatorioExecucao()
