import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def limpar_alertas(driver, tentativas=3):

    for i in range(tentativas):
        try:
            WebDriverWait(driver, 2).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            print(f"Pop-up aceito: {alert.text}")
            alert.accept()
            time.sleep(1)
        except TimeoutException:
            break
