import json
import os
import re
import sqlite3
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).parent
DB = Path(os.environ.get('SALES_DB', str(ROOT / 'data' / 'sales.sqlite3')))


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('''CREATE TABLE IF NOT EXISTS sales (
      id INTEGER PRIMARY KEY, product TEXT NOT NULL, quantity INTEGER NOT NULL,
      price INTEGER NOT NULL, cost INTEGER, sold_on TEXT NOT NULL)''')
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
        cursor = conn.execute('UPDATE sales SET product=?,quantity=?,price=?,cost=?,sold_on=? WHERE id=?',
                              (*values, sale_id))
        if not cursor.rowcount:
            raise LookupError('Venda não encontrada. Ela pode ter sido excluída em outra janela.')


def delete_sale(sale_id):
    with connect() as conn:
        cursor = conn.execute('DELETE FROM sales WHERE id=?', (sale_id,))
        if not cursor.rowcount:
            raise LookupError('Venda não encontrada. Ela pode ter sido excluída em outra janela.')


def dashboard(start, end):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start > end or (end - start).days > 366:
        raise ValueError('Selecione um período de até 367 dias, com início antes do fim.')
    length = (end - start).days + 1
    prev_start, prev_end = start - timedelta(days=length), start - timedelta(days=1)
    with connect() as conn:
        rows = [dict(r) for r in conn.execute('SELECT * FROM sales WHERE sold_on BETWEEN ? AND ? ORDER BY sold_on DESC,id DESC', (start.isoformat(), end.isoformat()))]
        previous = conn.execute('SELECT COALESCE(SUM(quantity*price),0),COUNT(*) FROM sales WHERE sold_on BETWEEN ? AND ?', (prev_start.isoformat(), prev_end.isoformat())).fetchone()
        lifetime = conn.execute('SELECT SUM(quantity*(price-cost)), COUNT(cost), COUNT(*), SUM(quantity*cost) FROM sales').fetchone()
    revenue = sum(r['quantity'] * r['price'] for r in rows)
    known = [r for r in rows if r['cost'] is not None]
    known_revenue = sum(r['quantity'] * r['price'] for r in known)
    profit = sum(r['quantity'] * (r['price'] - r['cost']) for r in known)
    margin = profit / known_revenue * 100 if known_revenue else None
    products, days = {}, {}
    for r in rows:
        key = r['product'].casefold()
        p = products.setdefault(key, {'name': r['product'], 'quantity': 0, 'revenue': 0, 'known_quantity': 0, 'profit': 0})
        p['quantity'] += r['quantity']; p['revenue'] += r['quantity'] * r['price']
        if r['cost'] is not None:
            p['known_quantity'] += r['quantity']
            p['profit'] += r['quantity'] * (r['price'] - r['cost'])
        days[r['sold_on']] = days.get(r['sold_on'], 0) + r['quantity'] * r['price']
    for p in products.values():
        p['unit_profit'] = p['profit'] / p['known_quantity'] if p['known_quantity'] else None
        if not p['known_quantity']:
            p['profit'] = None
    daily = [{'date': (start + timedelta(days=i)).isoformat(), 'revenue': days.get((start + timedelta(days=i)).isoformat(), 0)} for i in range(length)]
    alerts = []
    if any(r['cost'] is not None and r['price'] < r['cost'] for r in rows):
        alerts.append({'level': 'danger', 'title': 'Vendas abaixo do custo', 'text': 'Há vendas com preço unitário menor que o custo informado. Confira preço, descontos e cadastro de custo.'})
    if margin is not None and margin < 20:
        alerts.append({'level': 'warning', 'title': 'Margem bruta abaixo de 20%', 'text': 'A margem das vendas com custo informado está baixa. Revise preços e custos; este limite inicial é uma referência, não uma meta da sua empresa.'})
    if len(known) < len(rows):
        alerts.append({'level': 'warning', 'title': 'Custos incompletos', 'text': 'Algumas vendas não têm custo. O lucro bruto exibido considera somente vendas com custo informado e não inclui despesas, impostos ou frete.'})
    change = (revenue / previous[0] - 1) * 100 if previous[0] else None
    if change is not None and change <= -20:
        alerts.append({'level': 'warning', 'title': 'Queda de faturamento de pelo menos 20%', 'text': 'Comparação com o período anterior de mesma duração. Verifique se todos os lançamentos estão completos e se o período atual já terminou.'})
    weekdays = []
    names = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    for index, name in enumerate(names):
        matches = [d for d in daily if date.fromisoformat(d['date']).weekday() == index]
        if matches:
            weekdays.append({'name': name, 'average': sum(d['revenue'] for d in matches) / len(matches), 'occurrences': len(matches)})
    return {'lifetime_profit': lifetime[0], 'lifetime_cost_count': lifetime[1], 'lifetime_count': lifetime[2],
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
        if not 0 < length <= 8192:
            raise ValueError('Tamanho de requisição inválido.')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Envie um objeto JSON.')
        return data

    def do_PUT(self):
        try:
            sale_id = self.sale_id()
            edit_sale(sale_id, self.read_sale())
            self.send_json(200, {'id': sale_id})
        except LookupError as error:
            self.send_json(404, {'error': str(error)})
        except (ValueError, TypeError) as error:
            self.send_json(400, {'error': str(error)})

    def do_DELETE(self):
        try:
            sale_id = self.sale_id()
            delete_sale(sale_id)
            self.send_json(200, {'id': sale_id})
        except LookupError as error:
            self.send_json(404, {'error': str(error)})

    def do_POST(self):
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
