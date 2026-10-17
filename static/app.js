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
let mutating = false;
function el(tag, text, cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function empty(target,text){$(target).replaceChildren(el('p',text,'empty'));}
async function refresh(){
 if(loading || mutating)return;loading=true;
 try{
  const response=await fetch('/api/dashboard?'+new URLSearchParams(selected));
  const d=await response.json();if(!response.ok)throw Error(d.error);
  $('error').textContent='';$('live').textContent='● Atualizado às '+new Date().toLocaleTimeString('pt-BR');
  $('revenue').textContent=brl(d.revenue);$('quantity').textContent=num(d.quantity);$('count').textContent=`${num(d.count)} lançamentos de venda`;
  $('ticket').textContent=brl(d.ticket);$('profit').textContent=d.profit===null?'Sem custos':brl(d.profit);
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
   for(const value of [p.name,num(p.quantity),brl(p.revenue),p.unit_profit===null?'Informe o custo':brl(p.unit_profit),p.profit===null?'Informe o custo':brl(p.profit),`${num(p.known_quantity)} de ${num(p.quantity)}${p.known_quantity<p.quantity?' • parcial':''}`])row.append(el('td',value));
   $('product-profits').append(row);
  }
  if(!d.products.length){const row=el('tr'),cell=el('td','Registre vendas com custo para acompanhar o lucro de cada produto.');cell.colSpan=6;row.append(cell);$('product-profits').append(row);}
  $('sales').replaceChildren();for(const sale of d.sales){
   const row=el('tr');for(const value of [dateLabel(sale.sold_on),sale.product,num(sale.quantity),brl(sale.price),brl(sale.quantity*sale.price),sale.cost===null?'Sem custo':brl(sale.price-sale.cost)])row.append(el('td',value));
   const actions=el('td',undefined,'sale-actions');
   const edit=el('button','Editar','secondary');edit.type='button';edit.setAttribute('aria-label',`Editar venda ${sale.id}: ${sale.product}`);edit.addEventListener('click',()=>startEdit(sale));
   const remove=el('button','Excluir','delete-sale');remove.type='button';remove.setAttribute('aria-label',`Excluir venda ${sale.id}: ${sale.product}`);remove.addEventListener('click',()=>removeSale(sale));
   actions.append(edit,remove);row.append(actions);$('sales').append(row);
  }
  if(!d.sales.length){const cell=el('td','Nenhuma venda neste período.');cell.colSpan=7;const row=el('tr');row.append(cell);$('sales').append(row);}
  $('sales-total').textContent=`${num(d.count)} REGISTROS`;
 }catch(e){$('error').textContent=e.message;$('live').textContent='Atualização indisponível';}finally{loading=false;}
}
$('filter').addEventListener('click',()=>{selected={start:$('start').value,end:$('end').value};refresh();});
function resetForm(){
 editingId=null;form.reset();form.elements.sold_on.value=localDate(new Date());
 $('form-title').textContent='Registrar uma venda';$('save-sale').textContent='Salvar venda';$('cancel-edit').hidden=true;
}
function startEdit(sale){
 if(mutating)return;
 if(editingId!==null && editingId!==sale.id && !confirm('Trocar a venda em edição? As alterações não salvas serão descartadas.'))return;
 editingId=sale.id;
 form.elements.product.value=sale.product;form.elements.quantity.value=sale.quantity;
 form.elements.price.value=(sale.price/100).toFixed(2);form.elements.cost.value=sale.cost===null?'':(sale.cost/100).toFixed(2);form.elements.sold_on.value=sale.sold_on;
 $('form-title').textContent=`Editar venda #${sale.id}`;$('save-sale').textContent='Salvar alterações';$('cancel-edit').hidden=false;
 $('form-status').textContent='Altere os campos e clique em Salvar alterações. Isso substitui a venda, sem duplicá-la.';
 $('new-sale').scrollIntoView({behavior:'smooth',block:'start'});form.elements.product.focus({preventScroll:true});
}
$('cancel-edit').addEventListener('click',()=>{resetForm();$('form-status').textContent='Edição cancelada. Nenhuma alteração foi salva.';});
function lockForm(locked){for(const control of form.elements)control.disabled=locked;}
async function removeSale(sale){
 if(mutating)return;
 if(!confirm(`Excluir a venda de ${sale.quantity} unidade(s) de “${sale.product}”, em ${dateLabel(sale.sold_on)}, total de ${brl(sale.quantity*sale.price)}? Essa ação não pode ser desfeita.`))return;
 mutating=true;lockForm(true);
 try{
  const response=await fetch(`/api/sales/${sale.id}`,{method:'DELETE'});const result=await response.json();if(!response.ok)throw Error(result.error);
  if(editingId===sale.id)resetForm();
  $('form-status').textContent='Venda excluída. Totais e rankings foram recalculados.';
 }catch(e){$('form-status').textContent=e.message;$('error').textContent=e.message;}
 finally{mutating=false;lockForm(false);await refresh();}
}
form.addEventListener('submit',async event=>{
 event.preventDefault();if(mutating)return;
 const values=Object.fromEntries(new FormData(form));values.quantity=Number(values.quantity);
 const wasEditing=editingId!==null;const path=wasEditing?`/api/sales/${editingId}`:'/api/sales';
 mutating=true;lockForm(true);$('form-status').textContent='Salvando…';
 try{
  const response=await fetch(path,{method:wasEditing?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});
  const result=await response.json();if(!response.ok)throw Error(result.error);
  resetForm();$('form-status').textContent=wasEditing?'Venda corrigida. Totais e lucros foram recalculados.':'Venda salva. Confira o período selecionado para vê-la no painel.';
 }catch(e){$('form-status').textContent=e.message;}
 finally{mutating=false;lockForm(false);await refresh();}
});
refresh();setInterval(refresh,5000);
