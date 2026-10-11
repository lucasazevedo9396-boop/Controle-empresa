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
        self.assertEqual(len(d['alerts']), 3)

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


if __name__ == '__main__':
    unittest.main()
