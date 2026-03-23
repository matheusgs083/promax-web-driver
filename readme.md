# Sistema de Automação do Promax

Este projeto é uma solução de automação robusta para o sistema legado **Promax**, desenvolvida em Python utilizando Selenium WebDriver (modo IE/Edge). O projeto segue estritamente o padrão de arquitetura **Page Object Model (POM)** para garantir escalabilidade, manutenção e leitura fácil.

## Organizacao

- `docs/` concentra contexto, revisao tecnica e plano de melhoria.
- `agents/` concentra prompts e instrucoes de agentes especializados.
- `pages/` e `core/` continuam sendo o codigo-fonte da automacao.

## Funcionalidades

* **Login Automático:** Suporte a frames, seleção dinâmica de unidades e injeção de Javascript para compatibilidade com sistemas legados (IE5/IE7 quirks mode).
* **Geração de Relatórios:**
    * Relatório de Vendas (030237).
    * Relatórios Gerenciais (0105070402, entre outros).


* **Tratamento de Janelas:** Gerenciamento automático de *pop-ups*, múltiplas janelas e alertas nativos.
* **Validação Visual:** Utiliza reconhecimento de imagem para confirmar sucessos (login, downloads) quando o DOM não é confiável.
* **Logs Detalhados:** Sistema de logs robusto (`logs/app.log`) para rastreabilidade de erros e execução.
* **Ferramenta de Mapeamento:** Crawler interno para mapear IDs e Names de novas telas automaticamente.

## Estrutura do Projeto (POM)

```
promax-web-driver/
├── core/                   # Núcleo da automação (não dependente de negócio)
│   ├── driver_factory.py   # Configuração do IEDriver/Edge Mode
│   ├── logger.py           # Configuração de logs
│   ├── mapeador.py         # Ferramenta de varredura de HTML (Scanner)
│   └── validador_visual.py # Validação por imagem
├── pages/                  # Page Objects (Regras de Negócio e Elementos)
│   ├── base_page.py        # Métodos genéricos (Click, Wait, JS Injection)
│   ├── login_page.py       # Lógica de Login e Unidades
│   ├── menu_page.py        # Navegação e Atalhos
│   ├── rotina_page.py      # Classe base para janelas de rotina
│   └── rotinas/            # Scripts específicos de cada relatório
│       ├── relatorio_030237_page.py
│       └── relatorio_0105070402_page.py
├── data/                   # Imagens para validação visual (.png)
├── logs/                   # Arquivos de log gerados
├── maps/                   # Arquivos .txt gerados pelo Mapeador
├── main.py                 # Ponto de entrada (Orquestrador)
└── .env                    # Variáveis de ambiente (Senhas e Configs)

```

## ⚙️ Pré-requisitos

1. **Python 3.10+** instalado.
2. **Navegador:** Microsoft Edge ou Internet Explorer configurado.
3. **Driver:** `IEDriverServer.exe` compatível com a versão do sistema operacional, colocado no PATH ou na pasta do projeto.

## 📦 Instalação

1. Clone o repositório:
```bash
git clone https://seu-repositorio.git
cd promax-web-driver-v2

```


2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate

```


3. Instale as dependências:
```bash
pip install -r requirements.txt

```
## 🔐 Configuração (.env)

Crie um arquivo `.env` na raiz do projeto. O sistema lê as configurações e **mapeia automaticamente** qualquer chave numérica como uma Unidade do Promax.

```ini
# Configurações do Sistema
PROMAX_URL=http://url.do.seu.sistema/promax
PROMAX_USER=seu_usuario
PROMAX_PASS=sua_senha

# Diretórios
DOWNLOAD_DIR=C:\Users\Public\Downloads
DRIVER_PATH=drivers\IEDriverServer.exe
EDGE_PATH=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe

# Mapeamento de Unidades (NOME=CODIGO)
PATOS=0640001
SUME=0640002
MATRIZ=0101001

```

## ▶️ Como Usar

### Executar o Robô Principal

Para rodar o fluxo completo definido no orquestrador:

```bash
python main.py

```

### Mapear uma Nova Rotina (Modo Desenvolvedor)

Se você precisa automatizar uma tela nova e não sabe os IDs dos campos:

1. No `main.py`, utilize a função de acesso genérico e chame o mapeador:
```python
janela = menu.acessar_rotina("CODIGO_DA_ROTINA")
from core.mapeador import mapear_campos
mapear_campos(janela.driver, "maps/novo_mapa.txt")

```

2. Execute o robô.
3. Verifique o arquivo gerado na pasta `maps/`. Ele conterá todos os `IDs`, `NAMEs` e `XPaths` da tela.

## 🛠️ Tecnologias e Decisões Técnicas

* **Selenium com Legacy JS:** Devido à idade do sistema Promax, métodos padrão do Selenium (`click`, `send_keys`) falham frequentemente. Implementamos injetores de Javascript puro (`execute_script`) na `BasePage` e `LoginPage` para garantir a interação com elementos antigos.
* **Blindagem contra `InvalidSelector`:** Uso de estratégias `By.NAME` e `By.XPATH` otimizadas para o IEDriver.
* **Wait Explícito:** Uso extensivo de `WebDriverWait` para garantir sincronia sem uso de `time.sleep` desnecessários.

## 📄 Licença

Este projeto é de uso interno e proprietário.

---
