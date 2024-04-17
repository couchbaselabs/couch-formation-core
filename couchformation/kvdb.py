##
##

import re
import os
import json
import logging
import sqlite3
import tempfile
from collections import UserDict

logger = logging.getLogger('couchformation.kvdb')
logger.addHandler(logging.NullHandler())


def connect(*args, **kwargs):
    return KeyValueStore(*args, **kwargs)


def documents(*args, **kwargs):
    return KeyValueStore(*args, **kwargs).documents()


class KeyValueStore(UserDict):

    def __init__(self, filename=None, tablename="kv"):
        super().__init__()
        self.temp_file = filename is None
        if filename:
            self.filename = filename
        else:
            f, self.filename = tempfile.mkstemp(prefix='kv_dict')
            os.close(f)
        self.tablename = tablename
        self.conn, self.cursor = self._connect()
        self._table(self.tablename)
        self.conn.create_function('REGEXP', 2, lambda exp, item: re.search(exp, item) is not None)

    def _table(self, tablename):
        self.conn.execute(f"""CREATE TABLE IF NOT EXISTS \"{tablename}\" (key TEXT PRIMARY KEY, value BLOB)""")

    def _connect(self):
        try:
            conn = sqlite3.connect(self.filename)
            cursor = conn.cursor()
            return conn, cursor
        except Exception as err:
            message = f"Can not initialize connection for file {self.filename}: {err}"
            logger.debug(message)
            raise RuntimeError(message)

    def _select(self, query, arg=None):
        if not arg:
            arg = ()
        self.cursor.execute(query, arg)
        return self.cursor.fetchall()

    def __enter__(self):
        if not hasattr(self, 'conn') or self.conn is None:
            self.conn, self.cursor = self._connect()
        return self

    def __exit__(self, *exc_info):
        self.close()

    def __str__(self):
        return f"KeyValueStore({self.filename}, {self.tablename})"

    def __repr__(self):
        return str(self)

    def __len__(self):
        rows = self._select(f"""SELECT COUNT(*) FROM \"{self.tablename}\"""")[0]
        return rows[0] if rows is not None else 0

    def __bool__(self):
        rows = self._select(f"""SELECT MAX(ROWID) FROM \"{self.tablename}\"""")[0]
        return True if rows[0] is not None else False

    def iterkeys(self):
        for row in self._select(f"""SELECT key FROM \"{self.tablename}\" ORDER BY rowid"""):
            yield row[0]

    def itervalues(self):
        for row in self._select(f"""SELECT value FROM \"{self.tablename}\" ORDER BY rowid"""):
            yield row[0]

    def iteritems(self):
        for row in self._select(f"""SELECT key, value FROM \"{self.tablename}\" ORDER BY rowid"""):
            yield row[0], row[1]

    def keys(self):
        return self.iterkeys()

    def values(self):
        return self.itervalues()

    def items(self):
        return self.iteritems()

    def __contains__(self, key):
        return self._select(f"""SELECT 1 FROM \"{self.tablename}\" WHERE key = ?""", (key,)) is not None

    def __getitem__(self, key):
        item = self._select(f"""SELECT value FROM \"{self.tablename}\" WHERE key = ?""", (key,))
        if len(item) == 0:
            return None
        return item[0][0]

    def __setitem__(self, key, value):
        self.conn.execute(f"""REPLACE INTO \"{self.tablename}\" (key, value) VALUES (?,?)""", (key, value))
        self.commit()

    def __delitem__(self, key):
        if key not in self:
            return
        self.conn.execute(f"""DELETE FROM \"{self.tablename}\" WHERE key = ?""", (key,))
        self.commit()

    @property
    def as_dict(self):
        d = {}
        for k, v in self.iteritems():
            d.update({k: v})
        return d

    def list_add(self, name, *args):
        data = self.list_get(name)
        data.append(args)
        new_list = json.dumps(data)
        self.conn.execute(f"""REPLACE INTO \"{self.tablename}\" (key, value) VALUES (?,?)""", (name, new_list))
        self.commit()

    def list_remove(self, name, match):
        data = self.list_get(name)
        new_data = [e for e in data if match not in e]
        new_list = json.dumps(new_data)
        self.conn.execute(f"""REPLACE INTO \"{self.tablename}\" (key, value) VALUES (?,?)""", (name, new_list))
        self.commit()

    def list_get(self, name):
        item = self._select(f"""SELECT value FROM \"{self.tablename}\" WHERE key = ?""", (name,))
        if len(item) == 0:
            current_list = '[]'
        else:
            current_list = item[0][0]
        data = json.loads(current_list)
        return data

    def list_element(self, name, match):
        data = self.list_get(name)
        for element in data:
            if match in element:
                return element
        return None

    def list_exists(self, name, match):
        data = self.list_get(name)
        for element in data:
            if match in element:
                return True
        return False

    def list_len(self, name):
        data = self.list_get(name)
        return len(data)

    def update(self, *args, **kwargs):
        if not args and not kwargs:
            return
        items = [(k, v) for k, v in kwargs.items()]
        for d in args:
            items.extend([(k, v) for k, v in d.items()])

        self.conn.executemany(f"""REPLACE INTO \"{self.tablename}\" (key, value) VALUES (?, ?)""", items)
        self.commit()

    def __iter__(self):
        return self.iterkeys()

    def clear(self):
        self.conn.commit()
        self.conn.execute(f"""DELETE FROM \"{self.tablename}\";""")
        self.conn.commit()

    def remove(self, name):
        self.conn.commit()
        try:
            self.conn.execute(f"""DROP TABLE \"{name}\";""")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def clean(self):
        self.cursor.execute("""SELECT name FROM sqlite_master WHERE type=\"table\"""")
        res = self.cursor.fetchall()
        for name in res:
            self.conn.commit()
            self.conn.execute(f"""DROP TABLE \"{name[0]}\";""")
            self.conn.commit()

    @staticmethod
    def get_document_names(filename):
        if not os.path.isfile(filename):
            raise IOError(f"file {filename} does not exist")
        with sqlite3.connect(filename) as conn:
            cursor = conn.execute("""SELECT name FROM sqlite_master WHERE type=\"table\"""")
            res = cursor.fetchall()
        return [name[0] for name in res]

    def document_len(self, name):
        rows = self._select(f"""SELECT COUNT(*) FROM \"{name}\"""")[0]
        return rows[0]

    def doc_id_startswith(self, text):
        self.cursor.execute(f"""SELECT name FROM sqlite_master WHERE type=\"table\" AND name LIKE '{text}%'""")
        res = self.cursor.fetchall()
        return [name[0] for name in res]

    def doc_id_match(self, pattern):
        self.cursor.execute(f"""SELECT name FROM sqlite_master WHERE type=\"table\" AND REGEXP(?, name)""", (pattern,))
        res = self.cursor.fetchall()
        return [name[0] for name in res]

    def key_match(self, pattern):
        self.cursor.execute(f"""SELECT key FROM \"{self.tablename}\" WHERE REGEXP(?, key)""", (pattern,))
        res = self.cursor.fetchall()
        return [value[0] for value in res]

    def value_match(self, pattern):
        self.cursor.execute(f"""SELECT value FROM \"{self.tablename}\" WHERE REGEXP(?, value)""", (pattern,))
        res = self.cursor.fetchall()
        return [value[0] for value in res]

    def document_exists(self, name):
        try:
            self._select(f"""SELECT COUNT(*) FROM \"{name}\"""")
            return True
        except sqlite3.OperationalError:
            return False

    @property
    def document_id(self):
        return self.tablename

    @property
    def file_name(self):
        return self.filename

    def document(self, name):
        self.tablename = name
        self._table(self.tablename)

    def documents(self):
        self.cursor.execute("""SELECT name FROM sqlite_master WHERE type=\"table\"""")
        res = self.cursor.fetchall()
        return [KeyValueStore(self.filename, name[0]) for name in res if self.document_len(name[0]) > 0]

    def commit(self):
        if self.conn is not None:
            self.conn.commit()

    def close(self):
        if hasattr(self, 'conn') and self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None
        if self.temp_file:
            try:
                os.remove(self.filename)
            except Exception as err:
                logger.debug(f"temp file delete: {err}")
                pass

    def terminate(self):
        self.close()
        if self.filename == ':memory:':
            return
        logger.info(f"deleting {self.filename}")
        try:
            if os.path.isfile(self.filename):
                os.remove(self.filename)
        except (OSError, IOError):
            logger.exception(f"failed to delete {self.filename}")

    def __del__(self):
        try:
            self.close()
        except Exception as err:
            logger.debug(f"deleting object: {err}")
            pass
