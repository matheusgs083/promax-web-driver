from pathlib import Path
from entrypoints.processes.extrair_logs_lote import executar_extracao

ARQUIVO_NBS = Path(__file__).parent / "data" / "nbs_lista.txt"


def carregar_nbs() -> list[str]:
    """Carrega a lista de NBs a partir do arquivo data/nbs_lista.txt se existir."""
    if ARQUIVO_NBS.exists():
        conteudo = ARQUIVO_NBS.read_text(encoding="utf-8")
        nbs = [linha.strip() for linha in conteudo.splitlines() if linha.strip()]
        if nbs:
            return nbs

    # Lista de fallback caso o arquivo não seja encontrado
    return ["14057", "16883", "16884"]


def main():
    nbs_para_consultar = carregar_nbs()
    mes_ano_filtro = "09/2026"

    # Permite sobrescrever interativamente se necessário
    if not nbs_para_consultar:
        print("=== EXTRAÇÃO EM LOTE DE LOGS PROMAX (PW01060P) ===")
        nbs_input = input("Digite os NBs separados por espaço ou vírgula: ")
        nbs_para_consultar = [nb.strip() for nb in nbs_input.replace(",", " ").split() if nb.strip()]

        mes_input = input("Digite o Mês/Ano (formato MM/AAAA, ex: 09/2026): ")
        if mes_input.strip():
            mes_ano_filtro = mes_input.strip()

    if not nbs_para_consultar:
        print("Erro: Nenhum NB foi informado. Encerrando.")
        return

    print(f"\n[+] Total de NBs carregados do arquivo data/nbs_lista.txt: {len(nbs_para_consultar)}")
    print(f"[+] Mês/Ano selecionado: {mes_ano_filtro}\n")

    executar_extracao(
        lista_nbs=nbs_para_consultar,
        mes_ano=mes_ano_filtro,
    )


if __name__ == "__main__":
    main()
