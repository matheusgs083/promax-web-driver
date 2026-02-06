from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


def selecionar_opcao_via_js(driver, elemento_select, valor_opcao):

    js_cmd = """
    var sel = arguments[0];
    var val = arguments[1];
    var encontrou = false;

    // 1. Itera para marcar a opção correta
    for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value == val) {
            sel.selectedIndex = i;
            encontrou = true;
            break;
        }
    }

    if (encontrou) {
        // 2. Dispara o evento de mudança (Crucial para o Promax)
        if (sel.fireEvent) {
            sel.fireEvent("onchange"); // Método IE Antigo
        } else if ("createEvent" in document) {
            var evt = document.createEvent("HTMLEvents");
            evt.initEvent("change", false, true);
            sel.dispatchEvent(evt);  // Método Padrão
        }
    }
    return encontrou;
    """
    resultado = driver.execute_script(js_cmd, elemento_select, valor_opcao)
    if resultado:
        print(f" > [JS] Opção '{valor_opcao}' selecionada com sucesso.")
    else:
        print(
            f" > [JS] AVISO: Opção '{valor_opcao}' não encontrada no select.")
