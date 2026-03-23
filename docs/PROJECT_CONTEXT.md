# Contexto do Projeto: promax-web-driver

## O que este projeto faz

Este repositório automatiza rotinas do sistema legado Promax usando Python, Selenium WebDriver e suporte a fluxos que dependem de comportamento antigo de IE/Edge em modo legado. O foco do projeto nao e um site moderno, e sim RPA operacional para executar tarefas internas de negocio com baixa confiabilidade de DOM, telas com frames, pop-ups, alertas nativos e downloads.

## Frentes principais do sistema

1. Relatorios Promax
   - Entry points: `mainRelatorios.py`, `mainRelatoriosFechamento.py` e `main.py`.
   - Geram relatorios operacionais e financeiros por rotina/codigo Promax.
   - Fazem reprocessamento de falhas ("repescagem"), consolidam execucao, renomeiam arquivos e movem saidas para diretorios de rede.
   - Rotinas mapeadas no codigo incluem `0512`, `0513`, `120601`, `120616`, `150501`, `030237` e `020220`.

2. Digitacao de pedidos
   - Entry point: `mainPedidos.py`.
   - Le pedidos de uma planilha Excel e automatiza a rotina `030104`.
   - Gera logs detalhados por item/pedido em `logs/pedidos`.

3. Alteracao em lote de condicao/CEMC
   - Entry point: `alterarCEMC.py`.
   - Le uma planilha Excel (`sheet_name="CEMC"`) e automatiza a rotina `03030701`.
   - Ajusta condicao de pagamento/serie para notas em lote.

## Arquitetura

- `core/`
  - Infraestrutura compartilhada: driver, configuracao, logs, rastreio de execucao, movimentacao e renomeacao de arquivos, validacao visual, mapeamento.
- `pages/`
  - Implementacao em Page Object Model.
  - `base_page.py`: primitivas de interacao.
  - `login_page.py`, `menu_page.py`, `rotina_page.py`: navegacao comum.
  - `pages/rotinas/`: objetos de pagina por rotina especifica do Promax.
- `data/`
  - Imagens de apoio para validacao visual e, em alguns fluxos, planilhas auxiliares.
- `logs/`
  - Saidas operacionais, consolidacoes e rastros de execucao.
- `maps/`
  - Artefatos gerados pelo mapeador de campos para novas telas.

## Como o projeto opera na pratica

- O login usa credenciais do `.env` via `core/settings.py`.
- A unidade de operacao muda conforme o fluxo:
  - `PROMAX_REPORT_UNIT` para relatorios.
  - `PROMAX_PEDIDOS_UNIT` para pedidos.
  - `PROMAX_LOTE_UNIT` para lote de condicao.
- Os scripts costumam seguir esta ordem:
  1. abrir navegador via `DriverFactory`
  2. fazer login no Promax
  3. acessar a rotina pelo menu
  4. preencher filtros ou dados da rotina
  5. baixar/gerar/processar resultado
  6. registrar status no tracker/log
  7. tentar auto-recuperacao em caso de queda de sessao
  8. renomear e mover arquivos quando aplicavel

## Particularidades tecnicas importantes

- O Promax e tratado como sistema legado: interacoes por Selenium puro podem falhar.
- O projeto usa bastante injecao de JavaScript, waits explicitos e validacao visual por imagem.
- Ha logica de retry e re-login para quedas de sessao, alertas inesperados e janelas perdidas.
- Os nomes de arquivos gerados carregam contexto de periodo, unidade e codigo da rotina.
- Parte relevante do valor de negocio esta na pos-processamento: consolidacao, higienizacao de nomes e movimentacao para pastas de rede usadas por outras areas/Power BI.

## Dependencias e ambiente

- Python com `selenium`, `python-dotenv`, `pandas`, `openpyxl`, `opencv-python`, `pyautogui`, `pywinauto`.
- Ambiente Windows.
- Dependencia operacional de Edge/IE mode, downloads locais e compartilhamentos de rede UNC.

## Arquivos mais importantes para entender manutencoes

- `core/settings.py`
- `core/driver_factory.py`
- `core/execution_result.py`
- `core/relatorio_execucao.py`
- `pages/base_page.py`
- `pages/login_page.py`
- `pages/menu_page.py`
- `pages/rotina_page.py`
- `pages/rotinas/*.py`
- `mainRelatorios.py`
- `mainRelatoriosFechamento.py`
- `main.py`
- `mainPedidos.py`
- `alterarCEMC.py`

## Heuristica rapida para futuras tarefas

- Se o problema envolver login, sessao, navegador ou compatibilidade legado: olhar `core/driver_factory.py`, `pages/base_page.py` e `pages/login_page.py`.
- Se o problema envolver uma rotina especifica do Promax: olhar o arquivo correspondente em `pages/rotinas/`.
- Se o problema envolver nomes, downloads ou destino final dos arquivos: olhar `core/manipulador_download.py`, `core/renomeador.py` e `core/movimentador.py`.
- Se o problema envolver configuracao: olhar `.env` e `core/settings.py`.
- Se o problema envolver comportamento geral do job: olhar o entry point correspondente.

## Resumo executivo

Este projeto e uma camada de automacao operacional para processos internos do Promax. Ele combina Page Object Model, estrategias de compatibilidade com sistema legado e pos-processamento de arquivos para sustentar fluxos reais de negocio, principalmente geracao de relatorios, digitacao de pedidos e alteracoes em lote baseadas em Excel.
