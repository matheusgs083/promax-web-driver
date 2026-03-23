# Core

Infraestrutura compartilhada do projeto, organizada por responsabilidade.

Subpastas:

- `browser/`
  - inicializacao e configuracao do IEDriver/Edge IE Mode
- `config/`
  - configuracoes de ambiente e paths do projeto
- `execution/`
  - contratos e helpers de execucao dos entrypoints
- `files/`
  - download visual, higienizacao e publicacao de arquivos
- `observability/`
  - logger e tracker de execucao
- `services/`
  - servicos de orquestracao, publicacao e pos-processamento
- `tools/`
  - utilitarios auxiliares, como mapeador e validacao visual

Essa estrutura reduz a poluicao da raiz de `core/` e deixa mais claro onde cada tipo de responsabilidade deve evoluir.
