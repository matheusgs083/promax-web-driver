# Worker remoto Promax

Este modo permite rodar um worker em outro PC usando somente este projeto
`promax-web-driver`. O `bot_api` fica centralizado no servidor, cuidando da fila,
agenda, logs e painel.

## Configuracao

No PC do worker, adicione ao `.env` deste projeto:

```dotenv
PROMAX_API_BASE_URL=http://IP-DO-SERVIDOR:8080
PROMAX_WORKER_TOKEN=token-configurado-no-bot-api
PROMAX_WORKER_ID=worker-sousa
```

Configure o usuario e a senha no painel central em `Promax Admin > Acesso ao
Promax`, usando exatamente o mesmo `PROMAX_WORKER_ID`. O `bot_api` envia essas
credenciais somente ao subprocesso da execucao atual, por `PROMAX_RUNTIME_USER`
e `PROMAX_RUNTIME_PASS`; elas tem prioridade sobre valores antigos no `.env`.

`PROMAX_USER` e `PROMAX_PASS` continuam aceitos apenas como fallback para uso
manual do driver fora da fila.

`PROMAX_DRIVER_DIR` e `PROMAX_PYTHON` sao opcionais. Quando nao informados, o
worker usa a propria pasta do `promax-web-driver` e o Python que iniciou o
script.

## Execucao

```powershell
python mainWorker.py
```

Para paralelismo real, use um worker por PC. A trava visual local continua
impedindo duas execucoes Promax simultaneas na mesma maquina.

Na maquina central da API, ajuste o limite global conforme a quantidade de PCs:

```dotenv
PROMAX_MAX_CONCURRENT_JOBS=2
```

Depois reinicie o `bot_api`.
