import sys
from entrypoints.processes.fechamento_mapa import main


if __name__ == "__main__":
    # Permite passar mapa via argumento da linha de comando ou padroniza em '93491'
    mapa_alvo = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "93741"
    main(mapa=mapa_alvo)
