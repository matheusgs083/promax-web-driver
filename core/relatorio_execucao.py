import csv
import os
import time
from datetime import datetime

class RelatorioExecucao:
    def __init__(self):
        self.registros = []
        # Inicia o cronômetro global assim que o robô começa a rodar
        self.inicio_total = time.time() 

    def anotar(self, rotina, unidade, status, detalhe, duracao_segundos=0):
        """Registra o resultado e o tempo de uma unidade na memória."""
        # Formata os segundos quebrados para o formato MM:SS
        minutos, segundos = divmod(int(duracao_segundos), 60)
        duracao_formatada = f"{minutos:02d}:{segundos:02d}"

        self.registros.append({
            "Hora": datetime.now().strftime("%H:%M:%S"),
            "Rotina": rotina,
            "Unidade": unidade,
            "Status": status,
            "Duração": duracao_formatada,
            "Detalhes": detalhe
        })

    def gerar_csv(self, diretorio_destino):
        """Exporta tudo que foi anotado para um arquivo Excel/CSV."""
        if not self.registros:
            return None
            
        os.makedirs(diretorio_destino, exist_ok=True)
        nome_arquivo = f"Log_Consolidado_{datetime.now().strftime('%d-%m-%Y_%H-%M')}.csv"
        caminho_completo = os.path.join(diretorio_destino, nome_arquivo)
        
        # Calcula o tempo total de execução do robô
        tempo_total_segundos = time.time() - self.inicio_total
        minutos_totais, segundos_totais = divmod(int(tempo_total_segundos), 60)
        horas_totais, minutos_totais = divmod(minutos_totais, 60)
        tempo_total_formatado = f"{horas_totais:02d}:{minutos_totais:02d}:{segundos_totais:02d}"
        
        with open(caminho_completo, mode='w', newline='', encoding='utf-8-sig') as arquivo:
            # Adicionamos a coluna "Duração"
            writer = csv.DictWriter(arquivo, fieldnames=["Hora", "Rotina", "Unidade", "Status", "Duração", "Detalhes"], delimiter=';')
            writer.writeheader()
            writer.writerows(self.registros)
            
            # Pula uma linha para separar os dados
            writer.writerow({})
            
            # Escreve a linha de Resumo Total no rodapé
            writer.writerow({
                "Hora": "",
                "Rotina": "RESUMO FINAL",
                "Unidade": "",
                "Status": "TEMPO TOTAL DO ROBÔ",
                "Duração": tempo_total_formatado,
                "Detalhes": f"Total de execuções: {len(self.registros)}"
            })
        
        return caminho_completo

tracker = RelatorioExecucao()