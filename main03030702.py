import sys

from entrypoints.processes.mapa_03030702 import main


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:
        main(mapa="93615")
