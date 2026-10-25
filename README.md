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
- Compras com até 100 itens e um pagamento por compra. O valor médio por compra considera cada compra nova como uma unidade e cada lançamento antigo como uma compra separada.
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

A primeira abertura atualiza o banco sem apagar as vendas e cria um backup SQLite consistente em `data/backups/antes-taxas-*.sqlite3` quando há dados anteriores. Preserve também seu backup manual e utilize apenas a nova versão após a atualização. As vendas no seu PC não são enviadas ao GitHub. Na seção **Vendas no período**, use **Editar** para preencher o formulário com a venda, **Salvar alterações** para corrigir ou **Cancelar edição** para desistir. **Excluir** pede confirmação e é permanente. A tabela **Quanto estou lucrando em cada produto?** acompanha o filtro de datas do painel.

## Pagamentos e taxas

A tela permite dinheiro, Pix, maquininha em débito/crédito e link de pagamento. A taxa é calculada sobre o valor total cobrado, não sobre o custo, e é estimada conforme a tabela fornecida pelo proprietário. Uma forma de pagamento por compra; não há pagamento dividido nesta versão. Pix e dinheiro não têm taxa informada e são calculados com zero. Não se presume que Pix seja gratuito em todo contrato.

| Bandeiras/canal | Débito | Crédito 1x a 12x (%) |
| --- | --- | --- |
| Visa / Mastercard | 1,37% | 3,15; 5,39; 6,12; 6,85; 7,57; 8,28; 8,99; 9,69; 10,38; 11,06; 11,74; 12,40 |
| Elo | 2,58% | 4,91; 6,47; 7,20; 7,92; 8,63; 9,33; 10,03; 10,72; 11,41; 12,08; 12,75; 13,41 |
| Amex / Hipercard | Não informado, bloqueado | 4,91; 6,47; 7,20; 7,92; 8,63; 9,33; 10,03; 10,72; 11,41; 12,08; 12,75; 13,41 |
| Link, todas as bandeiras | Não disponível | 4,20; 6,09; 7,01; 7,91; 8,80; 9,67; 12,59; 13,42; 14,25; 15,06; 15,87; 16,66 |

O percentual é aplicado uma única vez ao total da compra, inclusive no parcelado, com arredondamento para o centavo mais próximo (metade para cima). A taxa é rateada pelo faturamento de cada item usando maiores restos, mantendo a soma exata. Não se multiplica a taxa pelo número de parcelas. O extrato real pode diferir conforme contrato ou regras da operadora.

O painel mantém o lucro bruto (venda menos custo) e acrescenta **lucro após taxas** (venda menos custo menos taxa), antes de outras despesas e impostos. O lucro fica parcial quando há custos faltantes. As taxas agregadas incluem todos os itens, mesmo sem custo informado. A média por unidade de taxa é total da taxa dividido pelas unidades; pode ter arredondamento de exibição, e o total em centavos prevalece.

Vendas antigas ficam com pagamento **não informado**, sem inventar taxas retroativas. Há aviso de cobertura; ao editar uma venda antiga e selecionar o pagamento correto, ela passa a ser uma compra com taxa. A edição de compra abre todos os itens; para remover apenas um, use **Remover item** e salve. **Excluir compra** exclui todos os itens após confirmação. Itens, pagamento e taxas são gravados numa transação, evitando compras pela metade. Os percentuais e valores calculados ficam registrados; as alterações de pagamento recalculam todas as taxas da compra.
