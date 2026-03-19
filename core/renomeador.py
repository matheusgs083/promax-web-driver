import os
import re
import json
import sys
import pandas as pd
from pathlib import Path

# --- HACK PARA RODAR DIRETO ---
sys.path.append(str(Path(__file__).resolve().parent.parent))
# ------------------------------

from core.logger import get_logger

logger = get_logger("RENOMEADOR")

def carregar_dicionario_revendas(caminho_excel_auxiliar):
    dicionario = {}
    
    if not os.path.exists(caminho_excel_auxiliar):
        logger.error(f"Arquivo auxiliar não encontrado: {caminho_excel_auxiliar}")
        return dicionario

    try:
        df = pd.read_excel(caminho_excel_auxiliar, dtype=str)
        df.columns = df.columns.str.strip()
        
        for _, row in df.iterrows():
            linha_limpa = {k: str(v).strip() for k, v in row.dropna().to_dict().items() if str(v).strip() != "" and str(v).strip() != "nan"}
            cod_original = linha_limpa.get('idRevenda')
            
            if cod_original:
                cod_7_digitos = str(cod_original).split('.')[0].zfill(7)
                dicionario[cod_7_digitos] = linha_limpa
                
        logger.info(f"Dicionário Excel carregado! {len(dicionario)} revendas mapeadas.")
        
    except Exception as e:
        logger.error(f"Falha ao ler planilha com Pandas: {e}")

    return dicionario

def limpar_nomes_relatorios(pasta_relatorios, caminho_excel_auxiliar):
    """Higieniza os nomes, cria pastas por rotina e move/substitui os arquivos."""
    logger.info("=== INICIANDO HIGIENIZAÇÃO E ORGANIZAÇÃO DOS ARQUIVOS ===")
    
    mapa_revendas = carregar_dicionario_revendas(caminho_excel_auxiliar)
    if not mapa_revendas:
        logger.warning("Higienização abortada por falta de dados no dicionário.")
        return

    pasta = Path(pasta_relatorios)
    caminho_log = pasta / ".log_renomeios.json"
    log_renomeios = {}

    if caminho_log.exists():
        try:
            with open(caminho_log, 'r', encoding='utf-8') as f:
                log_renomeios = json.load(f)
        except Exception:
            pass

    arquivos_processados = 0
    
    for arquivo in pasta.iterdir():
        if arquivo.is_file() and arquivo.suffix.lower() == '.csv':
            nome_original = arquivo.name
            
            # Ignora o log consolidado ou arquivos ocultos
            if nome_original.startswith('.') or "Log_Consolidado" in nome_original:
                continue
            
            pasta_sub = None
            novo_nome = nome_original
            
            # Tenta descobrir o código da revenda no final do arquivo (Ex: _0640001.csv)
            match_revenda = re.search(r'_?(\d{7})\.csv$', nome_original, re.IGNORECASE)
            
            if match_revenda:
                cod = match_revenda.group(1)
                
                if cod in mapa_revendas:
                    row = mapa_revendas[cod]
                    
                    # 1. Substitui a tag (nUnidade) pelo número da filial -> (1)
                    if "(nUnidade)" in novo_nome and "nUnidade" in row:
                        n_unidade = row["nUnidade"]
                        novo_nome = novo_nome.replace("(nUnidade)", f"({n_unidade})")
                    
                    # 2. Descobre qual coluna do Excel usar e extrai o Nº da Rotina para criar a pasta
                    for coluna, valor_real in row.items():
                        if coluna.startswith("nomeUnidade") and valor_real:
                            padrao_lixo = f"{coluna}_{cod}" 
                            if padrao_lixo in novo_nome:
                                novo_nome = novo_nome.replace(padrao_lixo, valor_real)
                                
                                # ---> A MÁGICA DO PREFIXO AQUI <---
                                # Se o arquivo tiver " - ", tudo antes do traço vira a pasta!
                                if " - " in nome_original:
                                    pasta_sub = nome_original.split(" - ")[0].strip()
                                else:
                                    # Fallback (caso esqueça do traço, extrai só os números como antes)
                                    match_rotina = re.search(r'nomeUnidade(\d+)', coluna)
                                    if match_rotina:
                                        pasta_sub = match_rotina.group(1)
                    
                    # ---> TROCA DE VÍRGULA POR PONTO NO NOME DO ARQUIVO AQUI <---
                    novo_nome = novo_nome.replace(',', '.')
                    novo_nome = re.sub(r'\s+', ' ', novo_nome).strip()

            else:
                # ---> A MÁGICA DO PREFIXO PARA ARQUIVOS GLOBAIS AQUI <---
                if " - " in nome_original:
                    pasta_sub = nome_original.split(" - ")[0].strip()
                else:
                    # Fallback para relatórios globais sem traço
                    match_global = re.search(r'^(\d{4,})', nome_original)
                    if match_global:
                        pasta_sub = match_global.group(1)
                
                # ---> TROCA DE VÍRGULA POR PONTO NO NOME DOS ARQUIVOS GLOBAIS <---
                novo_nome = novo_nome.replace(',', '.')

            # Se conseguiu descobrir de qual rotina o arquivo é, move ele pra pasta!
            if pasta_sub:
                diretorio_rotina = pasta / pasta_sub
                diretorio_rotina.mkdir(exist_ok=True) # Cria a pasta se não existir
                
                caminho_novo = diretorio_rotina / novo_nome
                chave_log = f"{pasta_sub}/{novo_nome}" # Ex: "120601/02-2026 (1) SOUSA.csv"
                
                # Se o arquivo ainda não estiver no lugar certo
                if caminho_novo.resolve() != arquivo.resolve():
                    try:
                        # Substitui o rename por replace para sobrescrever arquivos existentes
                        arquivo.replace(caminho_novo)
                        logger.info(f"Organizado/Substituído: '{nome_original}' -> '{pasta_sub}/{novo_nome}'")
                        
                        # Anota no log a estrutura de pastas para poder reverter depois
                        log_renomeios[chave_log] = nome_original
                        arquivos_processados += 1
                        
                    except Exception as e:
                        logger.error(f"Erro ao organizar '{nome_original}': {e}")

    # Salva o arquivo de "memória" para o Ctrl+Z funcionar
    if arquivos_processados > 0:
        with open(caminho_log, 'w', encoding='utf-8') as f:
            json.dump(log_renomeios, f, indent=4, ensure_ascii=False)

    logger.info(f"Organização concluída. {arquivos_processados} arquivo(s) processado(s) e movidos/substituídos nas pastas.")

def desfazer_renomeacoes(pasta_relatorios):
    """Lê o log, devolve os arquivos para a raiz com o nome feio original e apaga as subpastas."""
    logger.info("=== INICIANDO MODO CTRL+Z (DESFAZER RENOMEAÇÕES E ORGANIZAÇÃO) ===")
    
    pasta = Path(pasta_relatorios)
    caminho_log = pasta / ".log_renomeios.json"
    
    if not caminho_log.exists():
        logger.warning("Nenhum log de renomeação encontrado. Não há nada para desfazer na pasta!")
        return
        
    try:
        with open(caminho_log, 'r', encoding='utf-8') as f:
            log_renomeios = json.load(f)
    except Exception as e:
        logger.error(f"Erro ao ler log de rollback: {e}")
        return
        
    arquivos_desfeitos = 0
    pastas_afetadas = set()
    
    for chave_log, nome_original in log_renomeios.items():
        # A chave log contém a subpasta (ex: "0513/23-02-2026 (1) SOUSA.csv")
        caminho_atual = pasta / chave_log
        caminho_antigo = pasta / nome_original # Volta o arquivo para a RAIZ
        
        if caminho_atual.exists():
            try:
                # Usa replace também no rollback para evitar erros se a raiz já tiver o arquivo
                caminho_atual.replace(caminho_antigo)
                logger.info(f"Restaurado para raiz: '{chave_log}' -> '{nome_original}'")
                arquivos_desfeitos += 1
                pastas_afetadas.add(caminho_atual.parent)
            except Exception as e:
                logger.error(f"Erro ao restaurar '{chave_log}': {e}")
                
    # Apaga as subpastas criadas se elas tiverem ficado vazias
    for dir_path in pastas_afetadas:
        if dir_path.exists() and dir_path.is_dir():
            try:
                # Só apaga se estiver vazia
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.info(f"Pasta vazia apagada: {dir_path.name}")
            except Exception:
                pass
                
    caminho_log.unlink(missing_ok=True)
    logger.info(f"Rollback finalizado! {arquivos_desfeitos} arquivo(s) voltaram para a raiz.")


# ==============================================================================
# BLOCO MAIN: Permite rodar o script sozinho pelo terminal
# ==============================================================================
if __name__ == "__main__":
    import dotenv
    
    dotenv.load_dotenv()
    
    projeto_raiz = Path(__file__).resolve().parent.parent
    pasta_destino = os.getenv("DOWNLOAD_DIR", r"C:\Users\caixa.patos\Documents\Relatorios")
    pasta_data = projeto_raiz / "data"
    
    arquivos_excel = list(pasta_data.glob("*.xlsx"))
    arquivos_excel = [f for f in arquivos_excel if not f.name.startswith("~$")]
    
    if not arquivos_excel:
        print("="*50)
        print(f"❌ ERRO CRÍTICO: Nenhum ficheiro .xlsx encontrado na pasta:\n{pasta_data}")
        print("="*50)
        exit()
        
    caminho_planilha = arquivos_excel[0] 
    
    print("="*50)
    print(" 🧹 FERRAMENTA DE HIGIENIZAÇÃO DE RELATÓRIOS (USANDO PANDAS 🐼)")
    print("="*50)
    print(f"📁 Pasta Alvo: {pasta_destino}")
    print(f"📊 Planilha Encontrada: {caminho_planilha.name}")
    print("-"*50)
    print("[1] - Renomear e Organizar Arquivos em Pastas")
    print("[2] - Desfazer Tudo (Voltar nomes e jogar pra raiz)")
    print("[0] - Sair")
    
    opcao = input("\nEscolha uma opção (0, 1 ou 2): ").strip()
    
    print("\n")
    if opcao == "1":
        limpar_nomes_relatorios(pasta_destino, str(caminho_planilha))
        print("\n✅ Processo de organização finalizado! Olhe a sua pasta de downloads.")
    elif opcao == "2":
        desfazer_renomeacoes(pasta_destino)
        print("\n⏪ Processo de reversão finalizado! Os arquivos voltaram à forma original.")
    else:
        print("Saindo sem fazer nada...")