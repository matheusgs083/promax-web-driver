# Orquestrador de Comunicados Academicos UEPB

Sistema proposto para organizar e automatizar o envio de comunicados por e-mail aos estudantes da UEPB, substituindo a dependencia de grupos informais de WhatsApp para avisos academicos.

## Descricao do Problema

Com o fim do grupo de WhatsApp utilizado para envio de avisos aos estudantes, a comunicacao academica passou a depender ainda mais do acesso manual ao site da UEPB e de repasses individuais. Esse processo pode fazer com que informacoes importantes, como editais, prazos, eventos, mudancas de calendario e avisos administrativos, passem despercebidas pelos alunos.

O problema afeta diretamente estudantes que precisam acompanhar comunicados institucionais com frequencia, mas nem sempre acessam o site da universidade diariamente. Tambem afeta coordenacoes, professores ou responsaveis por comunicacao, que precisam de um meio organizado para enviar avisos sob demanda.

## Objetivos

### Objetivo Geral

Desenvolver uma solucao em Java para monitorar publicacoes no site da UEPB e orquestrar o envio de e-mails aos estudantes cadastrados.

### Objetivos Especificos

- Monitorar o site da UEPB em busca de novas publicacoes relevantes.
- Identificar comunicados ainda nao enviados.
- Enviar e-mails automaticamente para os estudantes cadastrados.
- Permitir o envio manual de comunicados sob demanda.
- Registrar historico de avisos enviados.
- Evitar duplicidade no envio de mensagens.
- Executar a aplicacao em ambiente Docker para facilitar instalacao e reproducao.

## Publico-Alvo

- Estudantes da UEPB.
- Coordenacoes de curso.
- Professores ou servidores responsaveis por comunicados academicos.
- Equipes administrativas que precisam enviar avisos para grupos de estudantes.

## Justificativa

A proposta busca melhorar a comunicacao entre a instituicao e os estudantes, oferecendo um canal mais organizado, rastreavel e confiavel que grupos de mensagens instantaneas. O uso de e-mail permite manter historico, reduzir perda de informacoes e facilitar o envio de comunicados formais.

## Estudo de Viabilidade Tecnica

A solucao e tecnicamente viavel utilizando Java, pois a linguagem possui recursos consolidados para criacao de APIs, tarefas agendadas, integracao com banco de dados, consumo de paginas web e envio de e-mails.

O Docker sera utilizado para padronizar o ambiente de execucao, reduzindo problemas de configuracao entre diferentes maquinas. A aplicacao podera ser executada em containers, junto com um banco de dados, permitindo instalacao mais simples e melhor organizacao do projeto.

### Possiveis Desafios

- Mudancas na estrutura do site da UEPB podem exigir ajustes no monitoramento.
- E-mails podem ser classificados como spam se o envio nao for configurado corretamente.
- A lista de estudantes precisa estar atualizada.
- O sistema deve evitar envio duplicado de comunicados.
- Dados pessoais dos estudantes devem ser tratados com seguranca.

## Levantamento de Requisitos

Os requisitos podem ser levantados por meio de:

- Observacao do problema causado pelo fim do grupo de WhatsApp.
- Entrevistas ou questionarios com estudantes.
- Analise dos tipos de avisos publicados no site da UEPB.
- Conversas com professores, coordenadores ou responsaveis por comunicacao.
- Estudo do fluxo atual de divulgacao de avisos academicos.

## Requisitos Funcionais

- Cadastrar estudantes e seus respectivos e-mails.
- Listar estudantes cadastrados.
- Monitorar periodicamente o site da UEPB.
- Detectar novas publicacoes ou comunicados.
- Enviar e-mails automaticos quando novos avisos forem encontrados.
- Permitir envio de e-mail sob demanda por um usuario autorizado.
- Registrar historico de mensagens enviadas.
- Consultar logs de envio.
- Bloquear envio duplicado de uma mesma publicacao.

## Requisitos Nao Funcionais

- A aplicacao deve ser desenvolvida em Java.
- A execucao deve ser suportada por Docker.
- O sistema deve proteger os dados dos estudantes.
- O envio de e-mails deve ser confiavel e rastreavel.
- A interface ou API deve ser simples de utilizar.
- O codigo deve ser organizado em camadas.
- A solucao deve permitir manutencao futura.
- O monitoramento deve executar em intervalos configuraveis.

## Especificacao da Solucao

A solucao sera composta por uma aplicacao Java responsavel por:

1. Consultar periodicamente o site da UEPB.
2. Identificar novas publicacoes relevantes.
3. Verificar se a publicacao ja foi enviada anteriormente.
4. Criar um comunicado com titulo, conteudo resumido e link da publicacao.
5. Enviar o comunicado por e-mail para os estudantes cadastrados.
6. Registrar o envio no historico.
7. Permitir que um usuario autorizado envie comunicados manuais.

## Arquitetura Planejada

```text
orquestrador-comunicados-uepb/
|-- src/
|   |-- main/
|   |   |-- java/
|   |   |   `-- br/edu/uepb/comunicados/
|   |   `-- resources/
|   `-- test/
|-- Dockerfile
|-- docker-compose.yml
|-- README.md
`-- pom.xml
```

### Componentes Previstos

- Backend Java para regras de negocio.
- Modulo de monitoramento do site da UEPB.
- Modulo de envio de e-mails.
- Banco de dados para estudantes, comunicados e historico.
- API ou interface administrativa para envio sob demanda.
- Docker para execucao padronizada.

## Tecnologias Utilizadas

- Java.
- Spring Boot.
- Maven.
- Docker.
- Docker Compose.
- Banco de dados PostgreSQL ou MySQL.
- JavaMailSender ou servico SMTP equivalente.
- Git e GitHub para versionamento.

## Execucao com Docker

> Esta secao descreve a forma planejada de execucao. Os comandos poderao ser ajustados conforme a implementacao do projeto.

```bash
docker compose up --build
```

Após a inicializacao, a aplicacao devera ficar disponivel na porta configurada no projeto, por exemplo:

```text
http://localhost:8080
```

## Qualidade de Software

A solucao considera os seguintes atributos de qualidade:

- Confiabilidade: registro de envios e controle para evitar mensagens duplicadas.
- Seguranca: protecao dos dados dos estudantes e restricao de acesso ao envio manual.
- Usabilidade: fluxo simples para envio sob demanda.
- Manutenibilidade: separacao entre monitoramento, envio de e-mails, cadastro e historico.
- Portabilidade: uso de Docker para facilitar execucao em diferentes ambientes.

## Resultados Esperados

Espera-se que o sistema reduza a perda de comunicados importantes, facilite o envio de avisos academicos e ofereca um historico organizado das mensagens enviadas. A solucao tambem deve diminuir a dependencia de grupos informais e tornar a comunicacao com os estudantes mais estruturada.

## Limitacoes

- O sistema depende da disponibilidade do site da UEPB.
- Alteracoes no layout do site podem exigir manutencao no monitoramento.
- A entrega dos e-mails depende da configuracao correta do servidor SMTP.
- A lista de estudantes precisa ser mantida atualizada.

## Demonstracao

A demonstracao do projeto podera apresentar:

- Cadastro de estudantes.
- Monitoramento de uma publicacao.
- Envio automatico de comunicado.
- Envio manual sob demanda.
- Consulta ao historico de e-mails enviados.

## Contribuicao dos Integrantes

Esta secao devera ser preenchida com a participacao de cada integrante do grupo, indicando responsabilidades como levantamento de requisitos, desenvolvimento backend, configuracao Docker, testes, documentacao e apresentacao.
