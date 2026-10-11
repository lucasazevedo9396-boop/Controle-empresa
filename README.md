# Pulso — Controle de vendas e faturamento

Primeira versão para lançamento manual de vendas, com painel atualizado a cada 5 segundos e armazenamento SQLite persistente. Sem dependências externas; requer Python 3.10+.

## Instalar no Windows

Instale Python 3.10 ou superior. No GitHub, use **Code → Download ZIP**, extraia o arquivo e abra **INICIAR.bat** na pasta extraída. O navegador abrirá automaticamente. Mantenha a janela do terminal aberta durante o uso.

## Executar

Na pasta do repositório:

```sh
python app.py
```

O servidor usa porta 8000 e interface local por padrão. `PORT`, `HOST` e `SALES_DB` permitem configurar porta, interface e caminho do banco. Os dados ficam em `data/sales.sqlite3` (ignorado pelo Git). Faça backups do banco com a API de backup do SQLite; não confie no Git para preservar vendas.

## Recursos e critérios

- Faturamento, unidades e valor médio por lançamento no período selecionado.
- Lucro **bruto parcial**, calculado somente nas vendas que têm custo. Despesas, impostos e frete não estão incluídos.
- Top 5 por quantidade vendida; empates usam faturamento e nome. Nomes iguais sem distinção de maiúsculas são agrupados.
- Dias fortes/fracos por faturamento; média por dia da semana inclui dias sem lançamentos como zero. Isso não prova ausência de vendas. Empates de data mostram a primeira ocorrência.
- Alertas para venda abaixo do custo, margem bruta abaixo de 20%, custos incompletos e queda de faturamento de pelo menos 20% frente ao período anterior de mesma duração. Limites são referências iniciais. Períodos incompletos e cadastros faltantes podem distorcer conclusões.
- Cada registro é uma linha de produto; não há agrupamento de itens em pedidos. O valor médio exibido não é ticket por pedido.
- Valores monetários são armazenados como centavos inteiros.

## Validação

```sh
python -m unittest discover -s tests -v
node --check static/app.js
```

## Uso compartilhado

Duas sessões conectadas ao mesmo servidor recebem as novas vendas pelo polling de 5 segundos. Esta versão ainda não tem login, perfis, edição/exclusão, integração com sistemas de vendas nem implantação pública. Para uso pela internet, adicionar autenticação e autorização e hospedar com HTTPS antes de expor o servidor. O servidor de desenvolvimento fica em loopback por padrão.
