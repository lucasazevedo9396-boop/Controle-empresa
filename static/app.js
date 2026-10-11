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
function el(tag, text, cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function empty(target,text){$(target).replaceChildren(el('p',text,'empty'));}
async function refresh(){
 if(loading)return;loading=true;
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
  $('sales').replaceChildren();for(const sale of d.sales){const row=el('tr');for(const value of [dateLabel(sale.sold_on),sale.product,num(sale.quantity),brl(sale.price),brl(sale.quantity*sale.price)])row.append(el('td',value));$('sales').append(row);}
  if(!d.sales.length){const cell=el('td','Nenhuma venda neste período.');cell.colSpan=5;const row=el('tr');row.append(cell);$('sales').append(row);}
  $('sales-total').textContent=`${num(d.count)} REGISTROS`;
 }catch(e){$('error').textContent=e.message;$('live').textContent='Atualização indisponível';}finally{loading=false;}
}
$('filter').addEventListener('click',()=>{selected={start:$('start').value,end:$('end').value};refresh();});
form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button');button.disabled=true;$('form-status').textContent='Salvando…';try{const values=Object.fromEntries(new FormData(form));values.quantity=Number(values.quantity);const response=await fetch('/api/sales',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(values)});const result=await response.json();if(!response.ok)throw Error(result.error);$('form-status').textContent='Venda salva. O painel será atualizado automaticamente.';form.elements.product.value='';form.elements.price.value='';form.elements.cost.value='';form.elements.quantity.value=1;await refresh();}catch(e){$('form-status').textContent=e.message;}finally{button.disabled=false;}});
refresh();setInterval(refresh,5000);
