from entrypoints.processes.mapa_030302 import main
from pages.processes.processo_030302_page import Processo030302Page


def pedir_mapa():
    while True:
        mapa = input("Informe o codigo do mapa para testar a 030302: ").strip()
        try:
            return Processo030302Page.normalizar_mapa(mapa)
        except ValueError as exc:
            print(f"{exc} Tente novamente.")


if __name__ == "__main__":
    main(mapa=pedir_mapa())
