import sqlite3
from pathlib import Path
import tempfile
import unittest
import app


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = app.DB
        app.DB = Path(self.temp.name) / 'sales.db'

    def tearDown(self):
        app.DB = self.old
        self.temp.cleanup()

    def order(self, **changes):
        data = dict(sold_on='2025-01-06', payment=dict(method='credit',brand='visa',installments=2),
                    items=[dict(product='Whey',quantity=1,price='100',cost='60'),dict(product='Barra',quantity=2,price='10',cost='7')])
        data.update(changes)
        return data

    def test_rates_match_supplied_table_and_reject_invalid_combinations(self):
        for brand in ('visa','mastercard'):
            self.assertEqual(app.payment_rate(dict(method='debit',brand=brand)),137)
            expected=[315,539,612,685,757,828,899,969,1038,1106,1174,1240]
            for n,value in enumerate(expected,1):
                self.assertEqual(app.payment_rate(dict(method='credit',brand=brand,installments=n)),value)
        for brand in ('elo','amex','hipercard'):
            for n,value in enumerate([491,647,720,792,863,933,1003,1072,1141,1208,1275,1341],1):
                self.assertEqual(app.payment_rate(dict(method='credit',brand=brand,installments=n)),value)
        self.assertEqual(app.payment_rate(dict(method='debit',brand='elo')),258)
        for n,value in enumerate([420,609,701,791,880,967,1259,1342,1425,1506,1587,1666],1):
            self.assertEqual(app.payment_rate(dict(method='link',installments=n)),value)
        for payment in [dict(method='debit',brand='amex'),dict(method='debit',brand='hipercard'),dict(method='credit',brand='other'),dict(method='credit',brand='visa',installments=13),dict(method='debit',brand='visa',installments=2)]:
            with self.assertRaises(ValueError): app.payment_rate(payment)

    def test_cart_fee_allocation_profit_and_edit_are_atomic(self):
        key=app.save_order(self.order())
        d=app.dashboard('2025-01-01','2025-01-31')
        self.assertEqual(d['order_count'],1)
        self.assertEqual(d['count'],2)
        self.assertEqual(d['revenue'],12000)
        self.assertEqual(d['fees'],647)
        self.assertEqual(d['after_fees'],3953)
        self.assertEqual(d['lifetime_after_fees'],3953)
        products={p['name']:p for p in d['products']}
        self.assertEqual(products['Whey']['fees'],539)
        self.assertEqual(products['Barra']['fees'],108)
        self.assertEqual(products['Barra']['unit_after_fees'],246)
        bad=self.order(items=[dict(product='Oops',quantity=0,price='2')])
        with self.assertRaises(ValueError): app.save_order(bad,key)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['revenue'],12000)
        app.save_order(self.order(payment=dict(method='cash',installments=1),items=[dict(product='Whey',quantity=2,price='100',cost='60')]),key)
        d=app.dashboard('2025-01-01','2025-01-31')
        self.assertEqual(d['fees'],0);self.assertEqual(d['after_fees'],8000);self.assertEqual(d['count'],1)
        app.delete_order(key)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['count'],0)

    def test_rounding_reconciles_even_with_small_items_and_zero_total(self):
        self.assertEqual(app.allocate_fees([1,1,1],1666),[0,0,0])
        self.assertEqual(sum(app.allocate_fees([3,3,3],1666)),1)
        self.assertEqual(app.allocate_fees([0,0],137),[0,0])
        for rate in [137,315,1666]:
            totals=[1,17,1500,2901,99]
            self.assertEqual(sum(app.allocate_fees(totals,rate)),(sum(totals)*rate+5000)//10000)

    def test_original_database_migrates_and_backs_up_without_changing_sales(self):
        with sqlite3.connect(app.DB) as c:
            c.execute('CREATE TABLE sales(id INTEGER PRIMARY KEY,product TEXT,quantity INTEGER,price INTEGER,cost INTEGER,sold_on TEXT)')
            c.execute("INSERT INTO sales VALUES(1,'Antiga',2,1000,744,'2025-01-06')")
        d=app.dashboard('2025-01-01','2025-01-31')
        self.assertEqual(d['profit'],512);self.assertEqual(d['fees'],0);self.assertEqual(d['legacy_count'],1)
        backups=list((app.DB.parent/'backups').glob('*.sqlite3'))
        self.assertEqual(len(backups),1)
        with sqlite3.connect(backups[0]) as c:
            self.assertEqual(c.execute('SELECT quantity FROM sales').fetchone()[0],2)
        app.dashboard('2025-01-01','2025-01-31')
        self.assertEqual(len(list((app.DB.parent/'backups').glob('*.sqlite3'))),1)
        data=self.order(legacy_id=1)
        app.save_order(data)
        d=app.dashboard('2025-01-01','2025-01-31')
        self.assertEqual(d['count'],2);self.assertEqual(d['legacy_count'],0)
        with self.assertRaises(LookupError):app.save_order(data)
        self.assertEqual(app.dashboard('2025-01-01','2025-01-31')['count'],2)
