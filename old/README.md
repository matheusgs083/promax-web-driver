# Arquivos antigos

Esta pasta guarda wrappers, scripts manuais e artefatos antigos que foram retirados da raiz do projeto.

Uso atual:

- `cli.py` e o orquestrador sao a entrada oficial para relatorios.
- `mainWorker.py` continua na raiz para iniciar o worker local.
- `mainMapeador.py` continua na raiz para uso direto do mapeador.

Os arquivos desta pasta nao devem ser usados em novos fluxos. Se algum deles voltar a ser necessario, prefira recriar a chamada pelo `cli.py` ou mover a logica para `entrypoints/`, `tools/` ou `tests/`.
