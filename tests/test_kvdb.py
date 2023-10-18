##
##

import os
import unittest
import tempfile
import couchformation.kvdb as kvdb
from couchformation.kvdb import KeyValueStore

current_dir = os.path.dirname(os.path.realpath(__file__))


def create_path(filename):
    filename = os.path.join(current_dir, "db", filename)
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    return filename


class TestMain(unittest.TestCase):

    def setUp(self):
        filename = create_path("kv_test.db")
        os.unlink(filename) if os.path.exists(filename) else True
        filename = create_path("kv_test_1.db")
        os.unlink(filename) if os.path.exists(filename) else True
        filename = create_path("kv_test_2.db")
        os.unlink(filename) if os.path.exists(filename) else True

    def tearDown(self):
        filename = create_path("kv_test.db")
        os.unlink(filename) if os.path.exists(filename) else True
        filename = create_path("kv_test_1.db")
        os.unlink(filename) if os.path.exists(filename) else True
        filename = create_path("kv_test_2.db")
        os.unlink(filename) if os.path.exists(filename) else True

    def test_basic(self):
        filename = create_path("kv_test_1.db")
        db = KeyValueStore(filename=filename)
        self.assertFalse(db)
        db['data'] = 'abcd'
        self.assertTrue(db)
        self.assertEqual(db.get('data'), 'abcd')
        self.assertEqual(len(db), 1)
        del db['data']
        self.assertEqual(len(db), 0)
        db['data1'] = 1
        db['data2'] = 2
        db['data3'] = 3
        self.assertTrue(db.get('data1'))
        self.assertFalse(db.get('data4'))
        r = db.keys()
        self.assertEqual(set(r), {'data1', 'data2', 'data3'})
        r = db.values()
        self.assertEqual(set(r), {1, 2, 3})
        for k, v in db.items():
            self.assertTrue(k in ('data1', 'data2', 'data3'))
            self.assertTrue(v in (1, 2, 3))
        db['null'] = None
        self.assertIsNone(db['null'])

    def test_with_statement(self):
        with KeyValueStore() as d:
            self.assertTrue(isinstance(d, KeyValueStore))
            self.assertEqual(dict(d), {})
            self.assertEqual(list(d), [])
            self.assertEqual(len(d), 0)

    @staticmethod
    def test_reopen_conn():
        filename = create_path("kv_test.db")
        db = KeyValueStore(filename=filename)
        with db:
            db['key'] = 'value'
            db.commit()
        with db:
            db['key'] = 'value'
            db.commit()

    @staticmethod
    def test_as_str():
        db = KeyValueStore()
        db.__str__()
        db.close()
        db.__str__()

    @staticmethod
    def test_as_repr():
        db = KeyValueStore()
        db.__repr__()

    def test_directory_notfound(self):
        folder = tempfile.mkdtemp(prefix='testing')
        os.rmdir(folder)
        with self.assertRaises(RuntimeError):
            KeyValueStore(filename=os.path.join(folder, 'nonexistent'))

    @staticmethod
    def test_commit_nonblocking():
        with KeyValueStore() as d:
            d['key'] = 'value'
            d.commit()

    def test_default_reuse_existing(self):
        filename = create_path("kv_test.db")
        orig_db = KeyValueStore(filename=filename)
        orig_db['key'] = 'value'
        orig_db.commit()
        orig_db.close()

        next_db = KeyValueStore(filename=filename)
        self.assertIn('key', next_db.keys())
        self.assertEqual(next_db['key'], 'value')

    def test_overwrite(self):
        filename = create_path("kv_test.db")
        orig_db = KeyValueStore(filename=filename, tablename='some_table')
        orig_db['key'] = 'value'
        orig_db.commit()
        orig_db.close()
        next_db = KeyValueStore(filename=filename, tablename='some_table')
        self.assertIn('key', next_db.keys())

    def test_irregular_table_names(self):
        def __test_irregular_table_names(tablename):
            filename = ':memory:'
            db = KeyValueStore(filename, tablename=tablename)
            db['key'] = 'value'
            db.commit()
            self.assertEqual(db['key'], 'value')
            db.close()

        __test_irregular_table_names('1number')
        __test_irregular_table_names('space in name')
        __test_irregular_table_names('snake_case')
        __test_irregular_table_names('kebab-case')

    def test_overwrite_2(self):
        filename = create_path("kv_test_2.db")
        orig_db_1 = KeyValueStore(filename=filename, tablename='one')
        orig_db_1['key'] = 'value'
        orig_db_1.commit()
        orig_db_1.close()

        orig_db_2 = KeyValueStore(filename=filename, tablename='two')
        orig_db_2['key'] = 'value'
        orig_db_2.commit()
        orig_db_2.close()

        next_db_1 = KeyValueStore(filename=filename, tablename='one')
        self.assertIn('key', next_db_1.keys())

        next_db_2 = KeyValueStore(filename=filename, tablename='two')
        self.assertIn('key', next_db_2.keys())

    def test_terminate(self):
        filename = create_path("kv_test_3.db")
        d = kvdb.connect(filename)
        d['abc'] = 'def'
        d.commit()
        self.assertEqual(d['abc'], 'def')
        d.terminate()
        self.assertFalse(os.path.isfile(filename))
