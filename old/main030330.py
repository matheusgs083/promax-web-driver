import sys
from entrypoints.processes.mapa_030330 import main


if __name__ == "__main__":
    mapa_alvo = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else "93804"
    main(mapa=mapa_alvo)
