# Atualização diária — diagnóstico de 14/09/2026

## Causa observada
O workflow de produção tinha um único agendamento: 10:17 UTC (07:17 Brasília).
A execução 34868144139 foi criada apenas às 16:21:54 UTC (13:21:54 Brasília),
mais de seis horas após o horário programado. A coleta durou 149 segundos,
registrou cobertura de 100%, 135 verificações, zero erros e zero mudanças.
Build, validação e push passaram. Commit publicado: 2e7af6b8a31982d70b0c6771a46aca7b24411b80.
A Vercel confirmou o deploy desse commit às 16:24:44 UTC.
Zero mudanças legislativas não significa ausência de verificação.

Não há evidência de interferência do PR comercial: ele não foi mesclado,
e o blob de scripts/update_legislation.py é idêntico entre produção e PR.
A causa técnica específica dentro da fila do GitHub não está disponível;
o atraso entre horário agendado e criação da execução está comprovado.

## Correções preparadas no PR #4
- Mantido 07:17 BRT; acrescentados 10:43, 14:43 e 18:43 BRT.
  Cada disparo realiza coleta completa. São oportunidades adicionais, não
  garantia de pontualidade do scheduler do GitHub.
- Checkout do estado mais recente da branch ao iniciar, evitando usar dados
  antigos quando uma execução ficou na fila; concorrência separada por branch.
- Build e validação continuam obrigatórios antes de publicar.
- Verificação explícita de data em Brasília, conclusão, cobertura e erros.
  Uma coleta parcial é publicada se o site é válido, mas o workflow fica vermelho.
- Dataset preservado em artifact por 14 dias quando o job falha.
- Autoteste offline original do coletor incluído no CI do PR, além dos testes
  comerciais, validação de páginas e teste de navegador.
- Dados de produção de 14/09 integrados na branch. HTML é regenerado pelo build
  na Vercel e no CI a partir desse dataset, preservando as páginas comerciais.
- Banco e SMTP são usados somente pela API/entrega comercial; o coletor e
  o build público não exigem essas credenciais.

## Evidências
- Produção: https://github.com/lcaladoferreira/monitor-legislativo/actions/runs/34868144139
- CI anterior aprovado, incluindo navegador: https://github.com/lcaladoferreira/monitor-legislativo/actions/runs/34737851365
- Deploy de hoje: https://vercel.com/lcaladoferreiras-projects/monitor-legislativo/ABNUAWE7DgVZLJUZKaqx6VM71Euy
- GitHub documenta atrasos e eventual descarte em alta carga:
  https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

O ambiente local está indisponível nesta sessão; a validação das alterações
desta revisão será executada no GitHub Actions e registrada no PR.
Não foi feito merge nem alterado o agendamento da main.
