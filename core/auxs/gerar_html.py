import os
from datetime import datetime
from selenium.webdriver.common.by import By

def gerar_html_da_pagina(driver, caminho_arquivo=None, incluir_url=True):

    if caminho_arquivo is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_arquivo = os.path.abspath(f"pagina_{ts}.html")

    html = driver.page_source
    url = getattr(driver, "current_url", "")

    with open(caminho_arquivo, "w", encoding="utf-8", errors="ignore") as f:
        if incluir_url:
            f.write(f"URL: {url}\n\n")
        f.write(html)

    return caminho_arquivo


# Exemplo de uso:
# (coloque isso depois do login/navegação, quando você estiver na tela que quer capturar)
#
# arquivo = gerar_html_da_pagina(driver, "promax_pagina.txt")
# print("HTML salvo em:", arquivo)
