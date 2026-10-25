import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent
DB = Path(os.environ.get('SALES_DB', str(ROOT / 'data' / 'sales.sqlite3')))

SCHEMA_LOCK = threading.Lock()
# Percentuais da imagem em centésimos de ponto percentual (137 = 1,37%).
RATES = {
    'visa': {'debit': 137, 'credit': [315,539,612,685,757,828,899,969,1038,1106,1174,1240]},
    'mastercard': {'debit': 137, 'credit': [315,539,612,685,757,828,899,969,1038,1106,1174,1240]},
    'elo': {'debit': 258, 'credit': [491,647,720,792,863,933,1003,1072,1141,1208,1275,1341]},
    'amex': {'credit': [491,647,720,792,863,933,1003,1072,1141,1208,1275,1341]},
    'hipercard': {'credit': [491,647,720,792,863,933,1003,1072,1141,1208,1275,1341]},
    'link': {'credit': [420,609,701,791,880,967,1259,1342,1425,1506,1587,1666]},
}


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('''CREATE TABLE IF NOT EXISTS sales (
      id INTEGER PRIMARY KEY, product TEXT NOT NULL, quantity INTEGER NOT NULL,
      price INTEGER NOT NULL, cost INTEGER, sold_on TEXT NOT NULL)''')
    with SCHEMA_LOCK:
        columns = {r['name'] for r in conn.execute('PRAGMA table_info(sales)')}
        if 'fee' not in columns:
            # Backup SQLite consistente antes da primeira migração com dados reais.
            if conn.execute('SELECT COUNT(*) FROM sales').fetchone()[0]:
                backup_dir = DB.parent / 'backups'
                backup_dir.mkdir(exist_ok=True)
                with sqlite3.connect(backup_dir / ('antes-taxas-' + uuid.uuid4().hex + '.sqlite3')) as backup:
                    conn.backup(backup)
            with conn:
                conn.execute('BEGIN IMMEDIATE')
                conn.execute('ALTER TABLE sales ADD COLUMN fee INTEGER NOT NULL DEFAULT 0')
                conn.execute('ALTER TABLE sales ADD COLUMN order_id TEXT')
        conn.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, payment TEXT NOT NULL, rate INTEGER NOT NULL)')
    return conn


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0 or number > Decimal('100000000'):
            raise ValueError('Valor monetário fora do limite.')
        if number != number.quantize(Decimal('.01')):
            raise ValueError('Use no máximo duas casas decimais.')
        return int(number * 100)
    except InvalidOperation:
        raise ValueError('Valor monetário inválido.')


def validate_sale(data):
    product = str(data.get('product', '')).strip()
    if not product or len(product) > 120:
        raise ValueError('Informe um produto com até 120 caracteres.')
    quantity = data.get('quantity')
    if type(quantity) is not int or not 1 <= quantity <= 100000:
        raise ValueError('Quantidade deve ser inteira entre 1 e 100.000.')
    sold_on = date.fromisoformat(data.get('sold_on', ''))
    if sold_on > date.today():
        raise ValueError('A data da venda não pode estar no futuro.')
    price = money(data.get('price'))
    cost = None if data.get('cost') in (None, '') else money(data['cost'])
    return product, quantity, price, cost, sold_on.isoformat()


def add_sale(data):
    values = validate_sale(data)
    with connect() as conn:
        cursor = conn.execute('INSERT INTO sales(product,quantity,price,cost,sold_on) VALUES(?,?,?,?,?)',
                              values)
        return cursor.lastrowid


def edit_sale(sale_id, data):
    values = validate_sale(data)
    with connect() as conn:
        if conn.execute('SELECT 1 FROM sales WHERE id=? AND order_id IS NOT NULL', (sale_id,)).fetchone():
            raise ValueError('Edite a compra inteira para recalcular as taxas.')
        cursor = conn.execute('UPDATE sales SET product=?,quantity=?,price=?,cost=?,sold_on=? WHERE id=?',
                              (*values, sale_id))
        if not cursor.rowcount:
            raise LookupError('Venda não encontrada. Ela pode ter sido excluída em outra janela.')


def delete_sale(sale_id):
    with connect() as conn:
        if conn.execute('SELECT 1 FROM sales WHERE id=? AND order_id IS NOT NULL', (sale_id,)).fetchone():
            raise ValueError('Exclua ou edite a compra inteira.')
        cursor = conn.execute('DELETE FROM sales WHERE id=?', (sale_id,))
        if not cursor.rowcount:
            raise LookupError('Venda não encontrada. Ela pode ter sido excluída em outra janela.')


def payment_rate(payment):
    if not isinstance(payment, dict):
        raise ValueError('Selecione a forma de pagamento.')
    method = payment.get('method')
    installments = payment.get('installments', 1)
    if type(installments) is not int or not 1 <= installments <= 12:
        raise ValueError('Parcelas devem estar entre 1 e 12.')
    if method in ('cash', 'pix', 'unknown'):
        if installments != 1:
            raise ValueError('Este pagamento não permite parcelas.')
        return 0
    brand = payment.get('brand')
    if method == 'link':
        return RATES['link']['credit'][installments-1]
    if brand not in RATES or brand == 'link':
        raise ValueError('Bandeira inválida.')
    if method == 'debit':
        if installments != 1 or 'debit' not in RATES[brand]:
            raise ValueError('Débito não disponível para esta bandeira ou parcelas.')
        return RATES[brand]['debit']
    if method == 'credit':
        return RATES[brand]['credit'][installments-1]
    raise ValueError('Forma de pagamento inválida.')


def allocate_fees(totals, rate):
    # Arredonda uma vez o total da compra; distribui centavos pelos maiores restos.
    total_fee = (sum(totals) * rate + 5000) // 10000
    fees = [value * rate // 10000 for value in totals]
    ranking = sorted(range(len(totals)), key=lambda i: (-(totals[i]*rate % 10000), i))
    for i in ranking[:total_fee-sum(fees)]:
        fees[i] += 1
    return fees


def save_order(data, order_id=None):
    items = data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 100 or any(not isinstance(i, dict) for i in items):
        raise ValueError('A compra deve ter de 1 a 100 itens.')
    payment = data.get('payment')
    rate = payment_rate(payment)
    values = [validate_sale(dict(item, sold_on=data.get('sold_on'))) for item in items]
    if sum(v[1]*v[2] for v in values) > 1000000000000:
        raise ValueError('Valor total da compra acima do limite.')
    fees = allocate_fees([v[1]*v[2] for v in values], rate)
    with connect() as conn:
        legacy_id = data.get('legacy_id')
        if legacy_id is not None:
            if type(legacy_id) is not int or order_id is not None:
                raise ValueError('Venda antiga inválida.')
            if not conn.execute('DELETE FROM sales WHERE id=? AND order_id IS NULL', (legacy_id,)).rowcount:
                raise LookupError('Venda antiga não encontrada ou já convertida.')
        if order_id is None:
            order_id = uuid.uuid4().hex
            conn.execute('INSERT INTO orders(id,payment,rate) VALUES(?,?,?)', (order_id,json.dumps(payment),rate))
        else:
            if not conn.execute('UPDATE orders SET payment=?,rate=? WHERE id=?', (json.dumps(payment),rate,order_id)).rowcount:
                raise LookupError('Compra não encontrada. Atualize o painel.')
            conn.execute('DELETE FROM sales WHERE order_id=?', (order_id,))
        conn.executemany('INSERT INTO sales(product,quantity,price,cost,sold_on,fee,order_id) VALUES(?,?,?,?,?,?,?)',
                         [(*v,fee,order_id) for v,fee in zip(values,fees)])
    return order_id


def delete_order(order_id):
    with connect() as conn:
        if not conn.execute('DELETE FROM orders WHERE id=?', (order_id,)).rowcount:
            raise LookupError('Compra não encontrada.')
        conn.execute('DELETE FROM sales WHERE order_id=?', (order_id,))


def dashboard(start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start > end or (end - start).days > 366:
        raise ValueError('Selecione um período de até 367 dias, com início antes do fim.')
    length = (end - start).days + 1
    prev_start, prev_end = start - timedelta(days=length), start - timedelta(days=1)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute('SELECT * FROM sales WHERE sold_on BETWEEN ? AND ? ORDER BY sold_on DESC,id DESC', (start.isoformat(), end.isoformat()))]
        previous = conn.execute('SELECT COALESCE(SUM(quantity*price),0),COUNT(*) FROM sales WHERE sold_on BETWEEN ? AND ?', (prev_start.isoformat(), prev_end.isoformat())).fetchone()
        lifetime = conn.execute('SELECT SUM(quantity*(price-cost)), COUNT(cost), COUNT(*), SUM(quantity*cost), COALESCE(SUM(fee),0), SUM(CASE WHEN cost IS NOT NULL THEN quantity*(price-cost)-fee END), SUM(CASE WHEN order_id IS NULL THEN 1 ELSE 0 END) FROM sales').fetchone()
        order_rows = {r['id']: dict(r) for r in conn.execute('SELECT * FROM orders')}
        unknown_orders = sum(r['n'] for r in conn.execute('SELECT orders.payment,COUNT(*) AS n FROM sales JOIN orders ON sales.order_id=orders.id GROUP BY orders.id') if json.loads(r['payment']).get('method') == 'unknown')
    for row in rows:
        order = order_rows.get(row['order_id'])
        row['payment'] = json.loads(order['payment']) if order else {'method':'unknown','installments':1}
        row['rate'] = order['rate'] if order else 0
    revenue = sum(r['quantity'] * r['price'] for r in rows)
    known = [r for r in rows if r['cost'] is not None]
    known_revenue = sum(r['quantity'] * r['price'] for r in known)
    profit = sum(r['quantity'] * (r['price'] - r['cost']) for r in known)
    margin = profit / known_revenue * 100 if known_revenue else None
    products, days = {}, {}
    for r in rows:
        key = r['product'].casefold()
        p = products.setdefault(key, {'name': r['product'], 'quantity': 0, 'revenue': 0, 'known_quantity': 0, 'profit': 0, 'fees': 0, 'after_fees': 0})
        p['quantity'] += r['quantity']; p['revenue'] += r['quantity'] * r['price']
        p['fees'] += r['fee']
        if r['cost'] is not None:
            p['after_fees'] += r['quantity'] * (r['price'] - r['cost']) - r['fee']
            p['known_quantity'] += r['quantity']
            p['profit'] += r['quantity'] * (r['price'] - r['cost'])
        days[r['sold_on']] = days.get(r['sold_on'], 0) + r['quantity'] * r['price']
    for p in products.values():
        p['unit_profit'] = p['profit'] / p['known_quantity'] if p['known_quantity'] else None
        p['unit_after_fees'] = p['after_fees'] / p['known_quantity'] if p['known_quantity'] else None
        if not p['known_quantity']:
            p['after_fees'] = None
            p['profit'] = None
    daily = [{'date': (start + timedelta(days=i)).isoformat(), 'revenue': days.get((start + timedelta(days=i)).isoformat(), 0)} for i in range(length)]
    alerts = []
    if any(r['cost'] is not None and r['price'] < r['cost'] for r in rows):
        alerts.append({'level': 'danger', 'title': 'Vendas abaixo do custo', 'text': 'Há vendas com preço unitário menor que o custo informado. Confira preço, descontos e cadastro de custo.'})
    if margin is not None and margin < 20:
        alerts.append({'level': 'warning', 'title': 'Margem bruta abaixo de 20%', 'text': 'A margem das vendas com custo informado está baixa. Revise preços e custos; este limite inicial é uma referência, não uma meta da sua empresa.'})
    if len(known) < len(rows):
        alerts.append({'level': 'warning', 'title': 'Custos incompletos', 'text': 'Algumas vendas não têm custo. O lucro bruto exibido considera somente vendas com custo informado e não inclui despesas, impostos ou frete.'})
    if any(r['cost'] is not None and r['quantity']*(r['price']-r['cost'])-r['fee'] < 0 for r in rows):
        alerts.append({'level':'danger','title':'Prejuízo após taxas de pagamento','text':'Há produtos cujo preço não cobre o custo e a taxa de pagamento. Confira o lucro após taxas por produto.'})
    change = (revenue / previous[0] - 1) * 100 if previous[0] else None
    if change is not None and change <= -20:
        alerts.append({'level': 'warning', 'title': 'Queda de faturamento de pelo menos 20%', 'text': 'Comparação com o período anterior de mesma duração. Verifique se todos os lançamentos estão completos e se o período atual já terminou.'})
    weekdays = []
    names = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    for index, name in enumerate(names):
        matches = [d for d in daily if date.fromisoformat(d['date']).weekday() == index]
        if matches:
            weekdays.append({'name': name, 'average': sum(d['revenue'] for d in matches) / len(matches), 'occurrences': len(matches)})
    return {'fees': sum(r['fee'] for r in rows), 'lifetime_fees': lifetime[4],
            'after_fees': sum(r['quantity']*(r['price']-r['cost'])-r['fee'] for r in known) if known else None,
            'lifetime_after_fees': lifetime[5], 'legacy_count': (lifetime[6] or 0) + unknown_orders,
            'order_count': len({r['order_id'] or str(r['id']) for r in rows}),
            'lifetime_profit': lifetime[0], 'lifetime_cost_count': lifetime[1], 'lifetime_count': lifetime[2],
            'lifetime_cost': lifetime[3], 'cost': sum(r['quantity'] * r['cost'] for r in known) if known else None,
            'revenue': revenue, 'quantity': sum(r['quantity'] for r in rows), 'count': len(rows),
            'ticket': revenue / len(rows) if rows else 0, 'profit': profit if known else None,
            'margin': margin, 'cost_count': len(known), 'change': change, 'previous_revenue': previous[0],
            'top': sorted(products.values(), key=lambda p: (-p['quantity'], -p['revenue'], p['name']))[:5],
            'products': sorted(products.values(), key=lambda p: (p['name'].casefold(), p['name'])),
            'daily': daily, 'weekdays': sorted(weekdays, key=lambda d: -d['average']),
            'strong': max(daily, key=lambda d: d['revenue']) if rows else None,
            'weak': min(daily, key=lambda d: d['revenue']) if rows else None,
            'alerts': alerts, 'sales': rows}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'static'), **kwargs)

    def send_json(self, status, value):
        raw = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/rates':
            return self.send_json(200, RATES)
        if parsed.path != '/api/dashboard':
            return super().do_GET()
        try:
            q = parse_qs(parsed.query)
            self.send_json(200, dashboard(q.get('start', [date.today().replace(day=1).isoformat()])[0], q.get('end', [date.today().isoformat()])[0]))
        except (ValueError, TypeError) as error:
            self.send_json(400, {'error': str(error)})

    def sale_id(self):
        match = re.fullmatch(r'/api/sales/([1-9][0-9]*)', self.path)
        if not match:
            raise LookupError('Venda não encontrada.')
        return int(match.group(1))

    def read_sale(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 131072:
            raise ValueError('Tamanho de requisição inválido.')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Envie um objeto JSON.')
        return data

    def do_PUT(self):
        if self.path.startswith('/api/orders/'):
            return self.order_request('PUT')
        try:
            sale_id = self.sale_id()
            edit_sale(sale_id, self.read_sale())
            self.send_json(200, {'id': sale_id})
        except LookupError as error:
            self.send_json(404, {'error': str(error)})
        except (ValueError, TypeError) as error:
            self.send_json(400, {'error': str(error)})

    def do_DELETE(self):
        if self.path.startswith('/api/orders/'):
            return self.order_request('DELETE')
        try:
            sale_id = self.sale_id()
            delete_sale(sale_id)
            self.send_json(200, {'id': sale_id})
        except LookupError as error:
            self.send_json(404, {'error': str(error)})
        except ValueError as error:
            self.send_json(400, {'error': str(error)})

    def order_request(self, method):
        try:
            if method == 'POST':
                order_id = save_order(self.read_sale())
            else:
                match = re.fullmatch(r'/api/orders/([a-f0-9]{32})', self.path)
                if not match:
                    raise LookupError('Compra não encontrada.')
                order_id = match.group(1)
                if method == 'PUT':
                    save_order(self.read_sale(), order_id)
                else:
                    delete_order(order_id)
            self.send_json(201 if method == 'POST' else 200, {'id':order_id})
        except LookupError as error:
            self.send_json(404, {'error':str(error)})
        except (ValueError, TypeError) as error:
            self.send_json(400, {'error':str(error)})

    def do_POST(self):
        if self.path == '/api/orders':
            return self.order_request('POST')
        if self.path != '/api/sales':
            return self.send_json(404, {'error': 'Rota não encontrada.'})
        try:
            data = self.read_sale()
            self.send_json(201, {'id': add_sale(data)})
        except (ValueError, TypeError) as error:
            self.send_json(400, {'error': str(error)})


if __name__ == '__main__':
    connect().close()
    ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8000'))), Handler).serve_forever()
