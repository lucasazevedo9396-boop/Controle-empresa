# Pulso — Controle de vendas e faturamento

Aplicativo para lançamento manual de vendas, com painel atualizado a cada 5 segundos e armazenamento SQLite persistente. Sem dependências externas; requer Python 3.10+.

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
- Soma do custo das mercadorias vendidas (custo unitário × quantidade), no período e em todo o histórico. Não é o total de compras de estoque: mercadorias ainda não vendidas não estão incluídas. Custos ausentes deixam o total parcial.
- Lucro bruto acumulado de todas as vendas, independente do filtro, e soma do lucro na seção Vendas no período. Totais com custos faltantes são identificados como parciais.
- Lucro **bruto parcial**, calculado somente nas vendas que têm custo. Despesas, impostos e frete não estão incluídos.
- Lucro bruto por produto: total em reais e média ponderada por unidade, apenas nas unidades com custo informado. Custos faltantes aparecem como cobertura parcial; custo zero é válido.
- Edição de produto, quantidade, preço, custo e data, sem duplicar vendas. Exclusão com confirmação; totais, ranking e lucros são recalculados.
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

Duas sessões conectadas ao mesmo servidor recebem as novas vendas pelo polling de 5 segundos. Esta versão ainda não tem login, perfis, integração com sistemas de vendas nem implantação pública. Para uso pela internet, adicionar autenticação e autorização e hospedar com HTTPS antes de expor o servidor. O servidor de desenvolvimento fica em loopback por padrão.

## Atualizar sem perder vendas (Windows)

1. Feche a janela preta do Pulso para parar o servidor.
2. Faça uma cópia de segurança da pasta inteira do programa, incluindo `data`.
3. Baixe o ZIP atualizado do GitHub e extraia em uma pasta separada.
4. Copie **somente `app.py` e a pasta `static`** da nova versão para dentro da pasta antiga (a que contém seus dados), aceitando substituir esses arquivos. Não exclua, substitua ou mova a pasta `data`.
5. Abra o `INICIAR.bat` da pasta antiga e pressione **Ctrl + F5** no navegador.

O formato do banco desta atualização é o mesmo da versão anterior; não há migração nem recriação dos dados. As vendas no seu PC não são enviadas ao GitHub. Na seção **Vendas no período**, use **Editar** para preencher o formulário com a venda, **Salvar alterações** para corrigir ou **Cancelar edição** para desistir. **Excluir** pede confirmação e é permanente. A tabela **Quanto estou lucrando em cada produto?** acompanha o filtro de datas do painel.
