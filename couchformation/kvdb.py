##
##

import os
import logging
import sqlite3
import tempfile
from collections import UserDict

logger = logging.getLogger('couchformation.kvdb')
logger.addHandler(logging.NullHandler())


def connect(*args, **kwargs):
    return KeyValueStore(*args, **kwargs)


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
        return f"SqliteDict({self.filename})"

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

    def update(self, items=(), **kwargs):
        try:
            items = items.items()
        except AttributeError:
            pass
        items = [(k, v) for k, v in items]

        self.conn.executemany(f"""REPLACE INTO \"{self.tablename}\" (key, value) VALUES (?, ?)""", items)
        if kwargs:
            self.update(kwargs)
        self.commit()

    def __iter__(self):
        return self.iterkeys()

    def clear(self):
        self.conn.commit()
        self.conn.execute(f"""DELETE FROM \"{self.tablename}\";""")
        self.conn.commit()

    @staticmethod
    def get_document_names(filename):
        if not os.path.isfile(filename):
            raise IOError(f"file {filename} does not exist")
        with sqlite3.connect(filename) as conn:
            cursor = conn.execute("""SELECT name FROM sqlite_master WHERE type=\"table\"""")
            res = cursor.fetchall()
        return [name[0] for name in res]

    def doc_id_list(self):
        self.cursor.execute("""SELECT name FROM sqlite_master WHERE type=\"table\"""")
        res = self.cursor.fetchall()
        return [name[0] for name in res]

    def commit(self):
        if self.conn is not None:
            self.conn.commit()

    def close(self):
        logger.debug(f"closing {self}")
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
