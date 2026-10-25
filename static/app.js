const $ = id => document.getElementById(id);
const brl = cents => new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(cents/100);
const num = n => new Intl.NumberFormat('pt-BR').format(n);
const today = new Date();
const localDate = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const dateLabel = s => s.split('-').reverse().join('/');
$('start').value = localDate(new Date(today.getFullYear(),today.getMonth(),1));
$('end').value = localDate(today);
const form = $('sale-form');
form.elements.sold_on.value = localDate(today);
form.elements.sold_on.max = localDate(today);
let selected = {start:$('start').value,end:$('end').value};
let loading = false;
let editingId = null;
let legacyId = null;
let rates = {};
let latestSales = [];
let mutating = false;
function el(tag, text, cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function empty(target,text){$(target).replaceChildren(el('p',text,'empty'));}
async function refresh(){
 if(loading || mutating)return;loading=true;
 try{
  const response=await fetch('/api/dashboard?'+new URLSearchParams(selected));
  const d=await response.json();if(!response.ok)throw Error(d.error);
  $('error').textContent='';$('live').textContent='● Atualizado às '+new Date().toLocaleTimeString('pt-BR');
  const profitText=(value,count)=>value===null?(count?'Informe os custos':brl(0)):brl(value);
  const coverageText=(known,count)=>count?`${num(known)} de ${num(count)} vendas com custo${known<count?' • Total parcial: faltam custos em algumas vendas.':''}`:'Nenhuma venda registrada.';
  $('lifetime-profit').textContent=profitText(d.lifetime_profit,d.lifetime_count);
  $('lifetime-cost').textContent=profitText(d.lifetime_cost,d.lifetime_count);
  $('period-cost').textContent=profitText(d.cost,d.count);
  $('lifetime-coverage').textContent=coverageText(d.lifetime_cost_count,d.lifetime_count);
  $('period-profit').textContent=profitText(d.profit,d.count);
  $('period-profit-coverage').textContent=coverageText(d.cost_count,d.count);
  latestSales=d.sales;
  $('lifetime-fees').textContent=brl(d.lifetime_fees);
  $('lifetime-after-fees').textContent=profitText(d.lifetime_after_fees,d.lifetime_count);
  $('period-fees').textContent=brl(d.fees);
  $('period-after-fees').textContent=profitText(d.after_fees,d.count);
  $('legacy-warning').textContent=d.legacy_count?`${d.legacy_count} lançamentos antigos sem pagamento informado: taxas não descontadas nesses itens.`:'Antes de outras despesas e impostos. Custos ausentes tornam o lucro parcial.';
  $('revenue').textContent=brl(d.revenue);$('quantity').textContent=num(d.quantity);$('count').textContent=`${num(d.order_count)} compras • ${num(d.count)} itens lançados`;
  $('ticket').textContent=brl(d.order_count?d.revenue/d.order_count:0);$('profit').textContent=d.profit===null?'Sem custos':brl(d.profit);
  $('margin').textContent=d.margin===null?'Informe os custos para calcular':`Margem: ${d.margin.toFixed(1)}% • ${d.cost_count}/${d.count} registros com custo`;
  $('change').textContent=d.change===null?'Sem base anterior para comparação':`${d.change>=0?'+':''}${d.change.toFixed(1)}% frente ao período anterior`;
  $('chart').replaceChildren();const max=Math.max(...d.daily.map(x=>x.revenue),1);
  for(const day of d.daily){const col=el('div',undefined,'bar-col');col.title=`${dateLabel(day.date)}: ${brl(day.revenue)}`;const bar=el('div',undefined,'bar');bar.style.height=`${day.revenue/max*160}px`;col.append(bar,el('small',day.date.slice(8)));$('chart').append(col);}
  $('top').replaceChildren();d.top.forEach((p,i)=>{const row=el('div',undefined,'rank');const body=el('div',undefined,'rank-body');body.append(el('strong',p.name),el('small',brl(p.revenue)+' em vendas'));row.append(el('span',String(i+1).padStart(2,'0'),'rank-number'),body,el('strong',`${num(p.quantity)} un.`));$('top').append(row);});
  if(!d.top.length)empty('top','Seu ranking começa com a primeira venda.');
  $('days').replaceChildren();if(d.strong){for(const [day,label,cls] of [[d.strong,'Dia mais forte','day-card'],[d.weak,'Dia mais fraco','day-card weak']]){const card=el('div',undefined,cls);card.append(el('span',label),el('strong',brl(day.revenue)),el('small',dateLabel(day.date)));$('days').append(card);}}else empty('days','Registre vendas para analisar os dias.');
  $('weekdays').replaceChildren();if(d.count)for(const day of d.weekdays){const row=el('div',undefined,'weekday');row.append(el('span',`${day.name} (${day.occurrences} dias)`),el('strong',brl(day.average)));$('weekdays').append(row);}
  $('alerts').replaceChildren();for(const a of d.alerts){const card=el('div',undefined,'alert '+a.level);card.append(el('strong',a.title),el('p',a.text));$('alerts').append(card);}
  if(!d.alerts.length){const card=el('div',undefined,'alert ok');card.append(el('strong',d.count?'Nenhum alerta nos critérios atuais':'Ainda não há dados para analisar'),el('p',d.count?'Continue acompanhando. A análise depende da cobertura e da qualidade dos lançamentos.':'Registre suas vendas e custos para receber observações sobre o negócio.'));$('alerts').append(card);}
  $('product-profits').replaceChildren();
  for(const p of d.products){
   const row=el('tr');
   for(const value of [p.name,num(p.quantity),brl(p.revenue),p.unit_profit===null?'Informe o custo':brl(p.unit_profit),p.profit===null?'Informe o custo':brl(p.profit),brl(p.fees/p.quantity),brl(p.fees),p.unit_after_fees===null?'Informe o custo':brl(p.unit_after_fees),p.after_fees===null?'Informe o custo':brl(p.after_fees),`${num(p.known_quantity)} de ${num(p.quantity)}${p.known_quantity<p.quantity?' • parcial':''}`])row.append(el('td',value));
   $('product-profits').append(row);
  }
  if(!d.products.length){const row=el('tr'),cell=el('td','Registre vendas com custo para acompanhar o lucro de cada produto.');cell.colSpan=10;row.append(cell);$('product-profits').append(row);}
  $('sales').replaceChildren();const groups=new Map();
  for(const sale of d.sales){const key=sale.order_id||`legacy-${sale.id}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(sale);}
  for(const items of groups.values()){
   const sale=items[0], heading=el('tr',undefined,'order-heading'),cell=el('td');cell.colSpan=9;
   const total=items.reduce((n,s)=>n+s.quantity*s.price,0),fee=items.reduce((n,s)=>n+s.fee,0);
   cell.append(el('strong',`${sale.order_id?'Compra #'+sale.order_id.slice(0,8):'Venda antiga #'+sale.id} • ${dateLabel(sale.sold_on)} • ${paymentLabel(sale.payment)} • Total ${brl(total)} • Taxa ${brl(fee)} (${(sale.rate/100).toFixed(2).replace('.',',')}%) `));
   const edit=el('button','Editar compra','secondary');edit.type='button';edit.addEventListener('click',()=>startEdit(items));
   const remove=el('button','Excluir compra','delete-sale');remove.type='button';remove.addEventListener('click',()=>removeSale(items));cell.append(edit,remove);heading.append(cell);$('sales').append(heading);
   for(const s of items){const row=el('tr');for(const value of [dateLabel(s.sold_on),s.product,num(s.quantity),brl(s.price),brl(s.quantity*s.price),s.cost===null?'Sem custo':brl(s.price-s.cost),brl(s.fee),s.cost===null?'Sem custo':brl(s.quantity*(s.price-s.cost)-s.fee),''])row.append(el('td',value));$('sales').append(row);}
  }
  if(!d.sales.length){const cell=el('td','Nenhuma venda neste período.');cell.colSpan=9;const row=el('tr');row.append(cell);$('sales').append(row);}
  $('sales-total').textContent=`${num(d.count)} REGISTROS`;
 }catch(e){$('error').textContent=e.message;$('live').textContent='Atualização indisponível';}finally{loading=false;}
}
$('filter').addEventListener('click',()=>{selected={start:$('start').value,end:$('end').value};refresh();});
function paymentLabel(p){
 const names={cash:'Dinheiro',pix:'Pix',debit:'Débito',credit:'Crédito',link:'Link de pagamento',unknown:'Pagamento não informado'};
 return `${names[p.method]||p.method}${['credit','debit'].includes(p.method)?' '+p.brand:''}${['credit','link'].includes(p.method)?' '+p.installments+'x':''}`;
}
function addItem(item={}){
 const row=el('div',undefined,'order-item');
 for(const [name,label,type,value] of [['product','Produto','text',item.product||''],['quantity','Quantidade','number',item.quantity||1],['price','Preço unitário (R$)','number',item.price===undefined?'':(item.price/100).toFixed(2)],['cost','Custo unitário (R$)','number',item.cost==null?'':(item.cost/100).toFixed(2)]]){
  const field=el('label',label),input=el('input');input.name=name;input.type=type;input.value=value;
  if(name!=='cost')input.required=true;
  if(name==='product'){input.maxLength=120;input.placeholder='Ex.: Whey protein 900 g';}else{input.min=name==='quantity'?'1':'0';input.max=name==='quantity'?'100000':'100000000';input.step=name==='quantity'?'1':'.01';}
  field.append(input);row.append(field);
 }
 const remove=el('button','Remover item','secondary');remove.type='button';remove.addEventListener('click',()=>{if($('order-items').children.length===1){$('form-status').textContent='A compra precisa ter ao menos um produto.';return;}row.remove();preview();});row.append(remove);$('order-items').append(row);preview();
}
function payment(){return {method:form.elements.method.value,brand:form.elements.brand.value,installments:Number(form.elements.installments.value||1)};}
function currentRate(p){
 if(['cash','pix','unknown'].includes(p.method))return 0;
 if(p.method==='link')return rates.link?.credit[p.installments-1];
 if(p.method==='debit')return rates[p.brand]?.debit;
 if(p.method==='credit')return rates[p.brand]?.credit[p.installments-1];
}
function configurePayment(){
 const method=form.elements.method.value;
 $('brand-field').hidden=!['credit','debit'].includes(method);$('installments-field').hidden=!['credit','link'].includes(method);
 for(const option of form.elements.brand.options)option.disabled=method==='debit'&&['amex','hipercard'].includes(option.value);
 if(method==='debit'&&['amex','hipercard'].includes(form.elements.brand.value))form.elements.brand.value='visa';
 if(!['credit','link'].includes(method))form.elements.installments.value='1';
 preview();
}
function preview(){
 const p=payment(),rate=currentRate(p);let total=0;
 for(const row of $('order-items').children){const value=name=>row.querySelector(`[name=${name}]`).value;total+=Math.round(Number(value('price')||0)*100)*Number(value('quantity')||0);}
 if(rate===undefined){$('payment-preview').textContent='Selecione a forma de pagamento para calcular a taxa.';return;}
 const fee=Math.floor((total*rate+5000)/10000);
 $('payment-preview').textContent=`Total da compra: ${brl(total)} • Taxa: ${(rate/100).toFixed(2).replace('.',',')}% = ${brl(fee)} • A receber: ${brl(total-fee)}${p.method==='unknown'?' • Taxa não informada':''}`;
}
function resetForm(){
 editingId=null;legacyId=null;form.reset();form.elements.sold_on.value=localDate(new Date());$('order-items').replaceChildren();addItem();configurePayment();
 $('form-title').textContent='Registrar uma compra';$('save-sale').textContent='Salvar compra';$('cancel-edit').hidden=true;
}
function startEdit(items){
 if(mutating)return;
 if((editingId||legacyId)&&!confirm('Descartar a edição atual e abrir esta compra?'))return;
 const sale=items[0];editingId=sale.order_id;legacyId=sale.order_id?null:sale.id;
 $('order-items').replaceChildren();items.forEach(addItem);form.elements.sold_on.value=sale.sold_on;
 form.elements.method.value=sale.payment.method;form.elements.brand.value=sale.payment.brand||'visa';form.elements.installments.value=String(sale.payment.installments||1);configurePayment();
 $('form-title').textContent='Editar compra';$('save-sale').textContent='Salvar alterações';$('cancel-edit').hidden=false;
 $('form-status').textContent='Você está editando todos os itens e o pagamento desta compra. As taxas serão recalculadas.';
 $('new-sale').scrollIntoView({behavior:'smooth',block:'start'});
}
$('add-item').addEventListener('click',()=>{if($('order-items').children.length<100)addItem();});
form.addEventListener('input',preview);form.elements.method.addEventListener('change',configurePayment);form.elements.brand.addEventListener('change',configurePayment);
$('cancel-edit').addEventListener('click',()=>{resetForm();$('form-status').textContent='Edição cancelada.';});
function lockForm(locked){for(const control of form.elements)control.disabled=locked;}
async function removeSale(items){
 if(mutating)return;const sale=items[0];
 if(!confirm(`Excluir esta compra inteira com ${items.length} item(ns), total ${brl(items.reduce((n,s)=>n+s.quantity*s.price,0))}? Não pode ser desfeito. Para remover só um produto, use Editar compra.`))return;
 mutating=true;lockForm(true);
 try{const response=await fetch(sale.order_id?`/api/orders/${sale.order_id}`:`/api/sales/${sale.id}`,{method:'DELETE'});const result=await response.json();if(!response.ok)throw Error(result.error);if(editingId===sale.order_id||legacyId===sale.id)resetForm();$('form-status').textContent='Compra excluída.';}
 catch(e){$('form-status').textContent=e.message;}finally{mutating=false;lockForm(false);await refresh();}
}
form.addEventListener('submit',async event=>{
 event.preventDefault();if(mutating)return;
 const items=Array.from($('order-items').children,row=>{const value=name=>row.querySelector(`[name=${name}]`).value;return {product:value('product'),quantity:Number(value('quantity')),price:value('price'),cost:value('cost')};});
 const data={items,sold_on:form.elements.sold_on.value,payment:payment()};if(legacyId!==null)data.legacy_id=legacyId;
 const path=editingId?`/api/orders/${editingId}`:'/api/orders';const method=editingId?'PUT':'POST';
 mutating=true;lockForm(true);$('form-status').textContent='Salvando…';
 try{const response=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);resetForm();$('form-status').textContent='Compra salva. Produtos e taxas foram atualizados.';}
 catch(e){$('form-status').textContent=e.message;}finally{mutating=false;lockForm(false);await refresh();}
});
async function init(){
 try{const response=await fetch('/api/rates');if(!response.ok)throw Error('Não foi possível carregar as taxas.');rates=await response.json();for(let i=1;i<=12;i++){const option=el('option',i===1?'À vista':`${i}x`);option.value=i;form.elements.installments.append(option);}resetForm();await refresh();setInterval(refresh,5000);}
 catch(e){$('error').textContent=e.message;$('save-sale').disabled=true;}
}
init();
