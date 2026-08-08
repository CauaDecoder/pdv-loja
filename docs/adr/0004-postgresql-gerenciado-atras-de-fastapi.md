---
status: accepted
---

# PostgreSQL gerenciado atras de FastAPI com contingencia offline no Tkinter

O PDV precisa ser acessado por mais de um computador, mas deve continuar vendendo quando a internet falhar. Foi decidido usar PostgreSQL e Supabase Auth gerenciados pelo Supabase, com FastAPI como unica interface de negocio; o Tkinter continuara como Terminal de venda e usara SQLite somente como cache e fila local assinada durante contingencia offline.

## Opcoes consideradas

- Manter SQLite como fonte compartilhada pela rede foi rejeitado por concorrencia e operacao remota.
- Conectar cada desktop diretamente ao PostgreSQL foi rejeitado por expor credenciais e espalhar regras de negocio.
- Migrar imediatamente todo o PDV para Web foi adiado para um projeto separado.
- Suportar PostgreSQL e MySQL desde o inicio foi rejeitado; o modulo de aplicacao permanecera independente, permitindo novo adapter apenas se surgir necessidade real.

## Consequencias

- PostgreSQL sera a unica fonte central apos o corte; clientes nao acessarao tabelas diretamente.
- Um unico Terminal podera registrar vendas offline, por ate um dia, e sincronizara comandos idempotentes em ordem quando a conexao voltar.
- Vendas realizadas nao serao rejeitadas por estoque insuficiente; saldo negativo gerara alerta configuravel e auditoria.
- O risco de perder vendas offline por falha fisica do disco foi aceito: o backup local sera manual e permanecerá no mesmo disco.
- O painel Web nao faz parte desta migracao; a API apenas preserva caminho para um projeto futuro.
