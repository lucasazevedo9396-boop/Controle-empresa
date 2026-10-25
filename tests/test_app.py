import tempfile
import unittest
from pathlib import Path
import app


class SalesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = app.DB
        app.DB = Path(self.temp.name) / 'sales.db'

    def tearDown(self):
        app.DB = self.old
        self.temp.cleanup()

    def sale(self, **changes):
        data = dict(product='Café', quantity=2, price='15.50', cost='10.00', sold_on='2025-01-06')
        data.update(changes)
        return app.add_sale(data)

    def test_revenue_ranking_margin_and_persistence(self):
        self.sale()
        self.sale(product='café', quantity=3, cost=None)
        self.sale(product='Pão', quantity=6, price='2', cost='1')
        d = app.dashboard('2025-01-06', '2025-01-12')
        self.assertEqual(d['revenue'], 8950)
        self.assertEqual(d['profit'], 1700)
        self.assertEqual(d['cost_count'], 2)
        self.assertEqual([p['quantity'] for p in d['top']], [6, 5])
        self.assertEqual(d['strong']['date'], '2025-01-06')
        self.assertEqual(d['weak']['revenue'], 0)
        self.assertEqual(d['count'], 3)
        self.assertTrue(any(a['title'] == 'Custos incompletos' for a in d['alerts']))

    def test_loss_and_revenue_drop_alerts(self):
        self.sale(sold_on='2025-01-05', price='100')
        self.sale(price='5', cost='10')
        d = app.dashboard('2025-01-06', '2025-01-06')
        self.assertEqual(d['change'], -95)
        self.assertEqual(d['profit'], -1000)
        self.assertEqual(len(d['alerts']), 4)

    def test_empty_dashboard_does_not_invent_insights(self):
        d = app.dashboard('2025-01-01', '2025-01-31')
        self.assertIsNone(d['strong'])
        self.assertIsNone(d['profit'])
        self.assertEqual(d['top'], [])
        self.assertEqual(d['alerts'], [])

    def test_invalid_sales_are_not_saved(self):
        for changes in [dict(quantity=0), dict(quantity=1.5), dict(price='nan'), dict(price='1.001'), dict(cost='-1'), dict(sold_on='2099-01-01'), dict(product=' ')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.sale(**changes)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['count'], 0)

    def test_period_and_money_validation(self):
        self.assertEqual(app.money('0.29'), 29)
        with self.assertRaises(ValueError):
            app.dashboard('2025-02-01','2025-01-01')
        with self.assertRaises(ValueError):
            app.dashboard('2020-01-01','2025-01-01')

    def test_product_profit_is_weighted_and_excludes_missing_cost(self):
        self.sale(quantity=2, price='10', cost='7.44')
        self.sale(product='CAFÉ', quantity=1, price='20', cost='10')
        self.sale(quantity=5, cost=None)
        self.sale(product='Sem custo', cost=None)
        self.sale(product='Prejuízo', price='2', cost='3')
        d = app.dashboard('2025-01-06','2025-01-06')
        products = {p['name'].casefold(): p for p in d['products']}
        coffee = products['café']
        self.assertEqual(coffee['quantity'], 8)
        self.assertEqual(coffee['known_quantity'], 3)
        self.assertEqual(coffee['profit'], 1512)
        self.assertEqual(coffee['unit_profit'], 504)
        self.assertIsNone(products['sem custo']['profit'])
        self.assertIsNone(products['sem custo']['unit_profit'])
        self.assertEqual(products['prejuízo']['unit_profit'], -100)
        self.assertEqual(app.dashboard('2025-01-07','2025-01-07')['products'], [])

    def test_edit_and_delete_recalculate_without_duplicate(self):
        sale_id = self.sale()
        other_id = self.sale(product='Creatina', quantity=1)
        app.edit_sale(sale_id, dict(product='Whey', quantity=4, price='20', cost='12', sold_on='2025-01-07'))
        d = app.dashboard('2025-01-07','2025-01-07')
        self.assertEqual(d['count'], 1)
        self.assertEqual(d['sales'][0]['id'], sale_id)
        self.assertEqual(d['revenue'], 8000)
        self.assertEqual(d['products'][0]['unit_profit'], 800)
        with self.assertRaises(ValueError):
            app.edit_sale(sale_id, dict(product='Whey', quantity=0, price='20', sold_on='2025-01-07'))
        self.assertEqual(app.dashboard('2025-01-07','2025-01-07')['revenue'], 8000)
        app.delete_sale(sale_id)
        self.assertEqual(app.dashboard('2025-01-07','2025-01-07')['products'], [])
        self.assertEqual(app.dashboard('2025-01-06','2025-01-06')['sales'][0]['id'], other_id)
        with self.assertRaises(LookupError):
            app.delete_sale(sale_id)
        with self.assertRaises(LookupError):
            app.edit_sale(sale_id, dict(product='Whey', quantity=1, price='20', sold_on='2025-01-07'))

    def test_lifetime_profit_ignores_period_and_recalculates(self):
        old_id = self.sale(sold_on='2024-12-01', quantity=2, price='10', cost='7.44')
        new_id = self.sale(quantity=3, price='20', cost='10')
        self.sale(product='Sem custo', cost=None)
        d = app.dashboard('2025-01-01', '2025-01-31')
        self.assertEqual(d['profit'], 3000)
        self.assertEqual(d['lifetime_profit'], 3512)
        self.assertEqual(d['lifetime_cost'], 4488)
        self.assertEqual(d['cost'], 3000)
        self.assertEqual(d['lifetime_count'], 3)
        self.assertEqual(d['lifetime_cost_count'], 2)
        self.assertEqual(app.dashboard('2023-01-01','2023-01-31')['lifetime_profit'], 3512)
        app.edit_sale(new_id, dict(product='Barra', quantity=2, price='5', cost='10', sold_on='2025-01-06'))
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['lifetime_profit'], -488)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['lifetime_cost'], 3488)
        app.delete_sale(old_id)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['lifetime_profit'], -1000)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['lifetime_cost'], 2000)

    def test_lifetime_empty_missing_and_zero_cost(self):
        self.assertIsNone(app.dashboard('2025-01-01','2025-01-31')['lifetime_profit'])
        self.sale(cost=None)
        d = app.dashboard('2025-01-01','2025-01-31')
        self.assertIsNone(d['lifetime_profit'])
        self.assertEqual(d['lifetime_cost_count'], 0)
        self.assertIsNone(d['lifetime_cost'])
        self.sale(quantity=2, price='5', cost='0')
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['lifetime_profit'], 1000)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['lifetime_cost'], 0)

    def test_http_edit_delete_and_invalid_requests(self):
        import threading
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def request(path, method, data=None):
            raw = json.dumps(data).encode() if data is not None else None
            req = Request(base + path, data=raw, method=method, headers={'Content-Type': 'application/json'})
            try:
                with urlopen(req) as r:
                    return r.status, json.load(r)
            except HTTPError as error:
                return error.code, json.load(error)
        try:
            data = dict(product='Barra', quantity=1, price='10', cost='7.44', sold_on='2025-01-06')
            status, created = request('/api/sales', 'POST', data)
            self.assertEqual(status, 201)
            path = f"/api/sales/{created['id']}"
            data['quantity'] = 3
            self.assertEqual(request(path, 'PUT', data)[0], 200)
            self.assertEqual(request('/api/dashboard?start=2025-01-06&end=2025-01-06','GET')[1]['revenue'], 3000)
            self.assertEqual(request(path, 'PUT', [1, 2])[0], 400)
            self.assertEqual(request('/api/sales/nope', 'DELETE')[0], 404)
            self.assertEqual(request(path, 'DELETE')[0], 200)
            self.assertEqual(request(path, 'PUT', data)[0], 404)
            self.assertEqual(request(path, 'DELETE')[0], 404)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
