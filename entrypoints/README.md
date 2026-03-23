# Entry Points

Esta pasta concentra a implementacao real dos fluxos executaveis do projeto.

Referencias relacionadas:

- [../core/README.md](../core/README.md): organizacao dos componentes de infraestrutura
- [../pages/README.md](../pages/README.md): organizacao dos page objects
- [../docs/README.md](../docs/README.md): contexto tecnico e historico do projeto

Mapeamento atual:

- `reports/`
  - fluxos de relatorios, fechamento, repescagem e o legado `140510`
- `processes/`
  - fluxos transacionais, como pedidos e lote de condicao
- `maintenance/`
  - operacoes de suporte, como reprocessamento de publicacao
- `tools/`
  - utilitarios operacionais, como o mapeador

Compatibilidade mantida:

- os arquivos `main*.py` e `alterarCEMC.py` da raiz continuam existindo como wrappers de compatibilidade externa

