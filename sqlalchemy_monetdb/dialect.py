import re
import typing
from typing import Optional
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy import sql, util
from sqlalchemy import types as sqltypes

from sqlalchemy import pool, exc
from sqlalchemy.engine import default, reflection, ObjectScope, ObjectKind

from sqlalchemy_monetdb.base import MonetExecutionContext, \
    MonetIdentifierPreparer
from sqlalchemy_monetdb.compiler import MonetDDLCompiler, MonetTypeCompiler, \
    MonetCompiler
from sqlalchemy_monetdb.monetdb_types import MONETDB_TYPE_MAP

if typing.TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection

try:
    import alembic

    class MonetImpl(alembic.ddl.impl.DefaultImpl):
        __dialect__ = 'monetdb'
except ImportError:
    pass

class MonetDialect(default.DefaultDialect):

    supports_statement_cache = False
    name = "monetdb"
    driver = "pymonetdb"

    preexecute_pk_sequences = True
    supports_pk_autoincrement = True
    supports_sequences = True
    sequences_optional = True
    supports_native_decimal = True
    supports_default_values = True
    supports_native_boolean = True
    supports_multivalues_insert = True
    poolclass = pool.SingletonThreadPool
    supports_unicode_statements = True
    postfetch_lastrowid = True
    supports_is_distinct_from = False

    statement_compiler = MonetCompiler
    ddl_compiler = MonetDDLCompiler
    execution_ctx_cls = MonetExecutionContext
    preparer = MonetIdentifierPreparer
    type_compiler = MonetTypeCompiler
    default_paramstyle = 'pyformat'

    def __init__(self, **kwargs):
        default.DefaultDialect.__init__(self, **kwargs)

    @classmethod
    def dbapi(cls):
        return __import__("pymonetdb", fromlist="sql")

    def create_connect_args(self, url):
        opts = url.translate_connect_args()
        return [], opts

    def create_execution_context(self, *args, **kwargs):
        return MonetExecutionContext(self, *args, **kwargs)

    def get_table_names(self, connection: "Connection", schema=None, **kw):
        """Return a list of table names for `schema`."""

        q = """
            SELECT name
            FROM sys.tables
            WHERE system = false
            AND type = 0
            AND schema_id = :schema_id
        """
        args = {"schema_id": self._schema_id(connection, schema)}
        return [row[0] for row in connection.execute(text(q), args)]

    @reflection.cache
    def get_temp_table_names(self, con: "Connection", **kw):
        # 30 is table type LOCAL TEMPORARY
        s = "SELECT tables.name FROM sys.tables WHERE schema_id = (select id from schemas where name = 'tmp') AND type = 30"
        rs = con.execute(text(s))
        return [row[0] for row in rs]

    def has_table(self, connection: "Connection", table_name, schema=None, **kw):
        # seems like case gets folded in pg_class...
        if schema is None:
            cursor = connection.execute(
                text(
                    "select name from sys.tables where system = false and type = 0 and name = :name"
                ), {'name': table_name})

        else:
            cursor = connection.execute(
                text(
                    "SELECT tables.name "
                    "FROM sys.tables, sys.schemas "
                    "WHERE tables.system = FALSE "
                    "AND tables.schema_id = schemas.id "
                    "AND type = 0 "
                    "AND tables.name = :name "
                    "AND schemas.name = :schema",
                    ), {'name': table_name, 'schema': schema})

        return bool(cursor.first())

    def has_sequence(self, connection: "Connection", sequence_name, schema=None, **kw):
        q = """
            SELECT id
            FROM sys.sequences
            WHERE name = :name
            AND schema_id = :schema_id
        """
        args = {
            "name": sequence_name,
            "schema_id": self._schema_id(connection, schema)
        }
        cursor = connection.execute(text(q), args)
        return bool(cursor.first())

    def get_sequence_names(self, connection: "Connection", schema: Optional[str] = None, **kw):
        """Return a list of all sequence names available in the database.

        :param connection: sqlalchemy connection
        :param schema: schema name to query, if not the default schema.

        .. versionadded:: 1.4
        """

        q = "SELECT name FROM sys.sequences"
        if schema:
            q += " AND schema_id = :schema_id"
        args = {
            "schema_id": self._schema_id(connection, schema)
        }
        cursor = connection.execute(text(q), args)
        return cursor.fetchall()

    @reflection.cache
    def _schema_id(self, con: "Connection", schema_name):
        """Fetch the id for schema"""

        if schema_name is None:
            schema_name = con.execute(text("SELECT current_schema")).scalar()

        query = """
                    SELECT id
                    FROM sys.schemas
                    WHERE name = :schema_name
                """
        args = {"schema_name": schema_name}
        cursor = con.execute(text(query), args)
        schema_id = cursor.scalar()
        if schema_id is None:
            raise exc.InvalidRequestError(schema_name)
        return schema_id

    @reflection.cache
    def _table_id(self, con: "Connection", table_name, schema_name=None):
        """Fetch the id for schema.table_name, defaulting to current schema if
        schema is None
        """
        q = """
            SELECT id
            FROM sys.tables
            WHERE name = :name
            AND schema_id = :schema_id
        """
        args = {
            "name": table_name,
            "schema_id": self._schema_id(con, schema_name)
        }
        c = con.execute(text(q), args)

        table_id = c.scalar()
        if table_id is None:
            raise exc.NoSuchTableError(table_name)

        return table_id

    def _get_columns(self, connection: "Connection", filter_names=[], schema=None, temp=0, tabletypes=[ 0, 1], **kw):
        ischema = schema
        columns = defaultdict(list)
        if len(tabletypes) == 0:
            return columns.items()
        if temp == 1:
            if not schema:
                ischema = 'tmp'
        for table_name in filter_names:
          q = ""
          args = {}
          if ischema:
            q = """select name, \"type\", digits, scale, nulls as \"null\", cdefault from sys.describe_columns(:schema, :table)"""
            q = """SELECT c.name, c."type", c.type_digits digits, c.type_scale scale, c."null", c."default" cdefault, c.number
                FROM sys.tables t, sys.schemas s, sys.columns c                                                                                                                           
                        WHERE c.table_id = t.id                                                                                                                                             
                        AND t.name = :table                                                                                                                                              
                        AND t.schema_id = s.id                                                                                                                                              
                        AND t.temporary = :temp
                        AND t.type in ( %s )
                        AND s.name = :schema                                                                                                                                             
                ORDER BY c.number;   
                """ % (", ".join(str(tt) for tt in tabletypes))
            args = {"table": table_name, "schema": ischema, "temp": temp}
          else:
            q = """select name, \"type\", digits, scale, nulls as \"null\", cdefault from sys.describe_columns(CURRENT_SCHEMA, :table)"""
            q = """SELECT c.name, c."type", c.type_digits digits, c.type_scale scale, c."null", c."default" cdefault, c.number
                FROM sys.tables t, sys.schemas s, sys.columns c                                                                                                                           
                        WHERE c.table_id = t.id                                                                                                                                             
                        AND t.name = :table                                                                                                                                              
                        AND t.schema_id = s.id                                                                                                                                              
                        AND t.temporary = :temp
                        AND t.type in ( %s )
                        AND s.name = CURRENT_SCHEMA
                ORDER BY c.number;   
                """ % (", ".join(str(tt) for tt in tabletypes))
            args = {"table": table_name, "temp": temp}
          c = connection.execute(text(q), args)

          if c.rowcount == 0:
              continue
          result = columns[(schema,table_name)] 
          for row in c:
            args = ()
            kwargs = {}
            name = row.name
            if row.type in ("char", "varchar"):
                args = (row.digits,)
            elif row.type == "decimal":
                args = (row.digits, row.scale)
            elif row.type == 'timestamptz':
                kwargs = {'timezone': True}
            col_type = MONETDB_TYPE_MAP.get(row.type, None)
            if col_type is None:
                raise TypeError("Can't resolve type {0} (column '{1}')".format(col_type, name))
            col_type = col_type(*args, **kwargs)

            # monetdb translates an AUTO INCREMENT into a sequence
            autoincrement = False
            if row.cdefault is not None:
                r = r"""next value for \"(\w*)\"\.\"(\w*)"$"""
                match = re.search(r, row.cdefault)
                if match is not None:
                    seq_schema = match.group(1)
                    seq = match.group(2)
                    autoincrement = True

            column = {
                "name": name,
                "type": col_type,
                "default": row.cdefault,
                "autoincrement": autoincrement,
                "nullable": row.null,
            }

            result.append(column)
        return columns.items()

    def get_columns(self, connection: "Connection", table_name, schema=None, **kw):
        data = self._get_columns(connection, [ table_name ], schema, temp=0, tabletypes=[0,1],  **kw);
        return self._value_or_raise(data, table_name, schema)                                                                                                                               
    
    def get_multi_columns(
        self, connection, schema, filter_names, scope, kind, **kw
    ):
        if scope is ObjectScope.ANY:
            default_data = self.get_multi_columns(connection, schema, filter_names, ObjectScope.DEFAULT, kind, **kw);
            temp_data = self.get_multi_columns(connection, schema, filter_names, ObjectScope.TEMPORARY, kind, **kw);
            data = dict(default_data)
            data.update(temp_data)
            return data
        temp = 0;
        if scope is ObjectScope.DEFAULT:
            temp = 0;
        elif scope is ObjectScope.TEMPORARY:
            temp = 1;
        tabletypes = []
        if not filter_names:
            filter_names = []
            if temp == 1:
                tabletypes.append(30);
                if ObjectKind.TABLE in kind:
                    filter_names += self.get_temp_table_names(connection)
            else:
                if ObjectKind.TABLE in kind:
                    filter_names += self.get_table_names(connection, schema)
                if ObjectKind.VIEW in kind:
                    filter_names += self.get_view_names(connection, schema)

        if temp == 0 and ObjectKind.TABLE in kind:
            tabletypes.append(0);
        if temp == 0 and ObjectKind.VIEW in kind:
            tabletypes.append(1);
        return self._get_columns(connection, filter_names, schema, temp=temp, tabletypes=tabletypes, **kw);

    def _value_or_raise(self, data, table, schema):
        try:
            return dict(data)[(schema, table)]
        except KeyError:
            raise exc.NoSuchTableError(
                f"{schema}.{table}" if schema else table
            ) from None

    def get_foreign_keys(self, connection: "Connection", table_name, schema=None, **kw):
        """Return information about foreign_keys in `table_name`.

        Given a string `table_name`, and an optional string `schema`, return
        foreign key information as a list of dicts with these keys:

        constrained_columns
          a list of column names that make up the foreign key

        referred_schema
          the name of the referred schema

        referred_table
          the name of the referred table

        referred_columns
          a list of column names in the referred table that correspond to
          constrained_columns

        name
          optional name of the foreign key constraint.

        **kw
          other options passed to the dialect's get_foreign_keys() method.

        """

        q = ""
        args = {}
        if schema:
            q = """select fk_s, fk_t, fk_c, o, fk, pk_s, pk_t, pk_c, on_update, on_delete from sys.describe_foreign_keys where fk_t = :table AND fk_s = :schema"""
            args = {"table": table_name, "schema": schema }
        else:
            q = """select fk_s, fk_t, fk_c, o, fk, pk_s, pk_t, pk_c, on_update, on_delete from sys.describe_foreign_keys where fk_t = :table AND fk_s = CURRENT_SCHEMA"""
            args = {"table": table_name }
        c = connection.execute(text(q), args)

        key_data = None
        constrained_columns = []
        referred_columns = []
        last_name = None
        ondelete = None
        onupdate = None

        # build result like (tobe implemented) get_multi_foreign_keys
        fkeys = defaultdict(list)
        results = fkeys[(schema,table_name)] 
        for row in c:
            if last_name is not None and last_name != row.fk:
                key_data["constrained_columns"] = constrained_columns
                key_data["referred_columns"] = referred_columns
                key_data["options"] = { k: v for k, v in [
                    ("onupdate", onupdate),
                    ("ondelete", ondelete),
                    #("initially", False),
                    #("deferrable", False),
                    #("match", "full"),
                 ]
                 if v is not None and v != "NO ACTION"
                }
                results.append(key_data)
                constrained_columns = []
                referred_columns = []
                ondelete = None
                onupdate = None

            if last_name is None or last_name != row.fk:
                key_data = {
                    "name": row.fk,
                    "referred_schema": row.pk_s if schema else None,
                    "referred_table": row.pk_t,
                }
                ondelete = row.on_delete
                onupdate = row.on_update

            last_name = row.fk
            constrained_columns.append(row.fk_c)
            referred_columns.append(row.pk_c)

        if key_data:
            key_data["constrained_columns"] = constrained_columns
            key_data["referred_columns"] = referred_columns
            key_data["options"] = { k: v for k, v in [
                    ("onupdate", onupdate),
                    ("ondelete", ondelete),
                    #("initially", False),
                    #("deferrable", False),
                    #("match", "full"),
                ]
                if v is not None and v != "NO ACTION"
            }
            results.append(key_data)

        data = fkeys.items()
        return self._value_or_raise(data, table_name, schema)

    def get_indexes(self, connection: "Connection", table_name, schema=None, **kw):
        """
        ReflectedIndex list
            column_names: List[str | None],
            column_sorting: NotRequired[Dict[str, Tuple[str]]],
            dialect_options: NotRequired[Dict[str, Any]],
            duplicates_constraint: NotRequired[str | None],
            expressions: NotRequired[List[str]],
            include_columns: NotRequired[List[str]],
            name: str | None,
            unique: bool
        """

        q = ""
        args = {}
        if schema:
            q = """select ind, sch, tbl, col, tpe from sys.describe_indices where tbl = :table AND sch = :schema
            union
                   select con as ind, sch, tbl, col, tpe from sys.describe_constraints where tbl = :table AND sch = :schema and tpe = 'UNIQUE'"""
            args = {"table": table_name, "schema": schema }
        else:
            q = """select ind, sch, tbl, col, tpe from sys.describe_indices where tbl = :table AND sch = CURRENT_SCHEMA
            union
                   select con as ind, sch, tbl, col, tpe from sys.describe_constraints where tbl = :table AND sch = CURRENT_SCHEMA and tpe = 'UNIQUE'"""
            args = {"table": table_name }
        c = connection.execute(text(q), args)

        index_data = None
        column_names = []
        last_name = None

        idxs = defaultdict(list)
        results = idxs[(schema,table_name)] 
        for row in c:
            if last_name is not None and last_name != row.ind:
                index_data["column_names"] = column_names
                results.append(index_data)
                column_names = []

            if last_name is None or last_name != row.ind:
                index_data = {
                    "name": row.ind,
                    "unique": True if row.tpe == 'UNIQUE' else False,
                    "include_columns": [],
                    "dialect_options": {},
                }

            last_name = row.ind
            column_names.append(row.col)

        if index_data:
            index_data["column_names"] = column_names
            results.append(index_data)

        data = idxs.items()
        return self._value_or_raise(data, table_name, schema)

    def do_commit(self, connection):
        if not(connection.autocommit):
            connection.commit()

    def do_rollback(self, connection):
        if not(connection.autocommit):
            connection.rollback()

    @reflection.cache
    def get_schema_names(self, con: "Connection", **kw):
        s = """
                SELECT name FROM sys.schemas ORDER BY name
            """
        c = con.execute(text(s))
        schema_names = [row[0] for row in c]
        return schema_names

    def get_view_definition(self, connection: "Connection", view_name, schema=None, **kw):
        """Return view definition.

        Given a :class:`.Connection`, a string
        `view_name`, and an optional string `schema`, return the view
        definition.
        """

        q = """
            SELECT query FROM sys.tables
            WHERE type = 1
            AND name = :name
            AND schema_id = :schema_id
        """
        args = {
            "name": view_name,
            "schema_id": self._schema_id(connection, schema)
        }
        return connection.execute(text(q), args)

    def get_view_names(self, connection: "Connection", schema=None, **kw):
        """Return a list of all view names available in the database.

        schema:
          Optional, retrieve names from a non-default schema.
        """
        q = """
            SELECT name
            FROM sys.tables
            WHERE type = 1
            AND schema_id = :schema_id
        """
        args = {"schema_id": self._schema_id(connection, schema)}
        return [row[0] for row in connection.execute(text(q), args)]

    def _get_default_schema_name(self, connection):
        """Return the string name of the currently selected schema from
        the given connection.

        This is used by the default implementation to populate the
        "default_schema_name" attribute and is called exactly
        once upon first connect.
        """
        return connection.execute(text("SELECT CURRENT_SCHEMA")).scalar()

    def get_pk_constraint(self, connection: "Connection", table_name, schema=None, **kw):
        """Return information about primary key constraint on `table_name`.

        Given a string `table_name`, and an optional string `schema`, return
        primary key information as a dictionary with these keys:

        constrained_columns
          a list of column names that make up the primary key

        name
          optional name of the primary key constraint.

        """
        q = """
        SELECT "objects"."name" AS col, keys.name AS name
                 FROM "sys"."keys" AS "keys",
                         "sys"."objects" AS "objects",
                         "sys"."tables" AS "tables",
                         "sys"."schemas" AS "schemas"
                 WHERE "keys"."id" = "objects"."id"
                         AND "keys"."table_id" = "tables"."id"
                         AND "tables"."schema_id" = "schemas"."id"
                         AND "keys"."type" = 0
                         AND "tables"."id" = :table_id
        """
        args = {"table_id": self._table_id(connection, table_name, schema)}
        c = connection.execute(text(q), args)
        table = c.fetchall()
        if table:
            cols = [c[0] for c in table]
            name = table[0][1]
            return {'constrained_columns': cols, 'name': name}
        else:
            return {}

    def get_unique_constraints(self, connection: "Connection", table_name, schema=None, **kw):
        """Return information about unique constraints in `table_name`.

        Given a string `table_name` and an optional string `schema`, return
        unique constraint information as a list of dicts with these keys:

        name
          the unique constraint's name

        column_names
          list of column names in order

        **kw
          other options passed to the dialect's get_unique_constraints() method.

        .. versionadded:: 0.9.0

        """
        q = """
        SELECT "objects"."name" AS col, keys.name AS name
                 FROM "sys"."keys" AS "keys",
                         "sys"."objects" AS "objects",
                         "sys"."tables" AS "tables",
                         "sys"."schemas" AS "schemas"
                 WHERE "keys"."id" = "objects"."id"
                         AND "keys"."table_id" = "tables"."id"
                         AND "tables"."schema_id" = "schemas"."id"
                         AND "keys"."type" = 1
                         AND "tables"."id" = :table_id
        """
        args = {"table_id": self._table_id(connection, table_name, schema)}
        c = connection.execute(text(q), args)
        table = c.fetchall()

        from collections import defaultdict

        col_dict = defaultdict(list)
        for col, name in table:
            col_dict[name].append(col)

        return [{'name': n, 'column_names': c} for n, c in col_dict.items()]

    def get_check_constraints(self, connection, table_name, schema=None, **kw):
        return []

    def get_isolation_level_values(self, dbapi_conn):
        return (
            "AUTOCOMMIT",
            "SERIALIZABLE",
        )

    def set_isolation_level(self, dbapi_connection, level):
        if level == "AUTOCOMMIT":
            dbapi_connection.set_autocommit(True)
        else:
            dbapi_connection.set_autocommit(False)
            #cursor = dbapi_connection.cursor()
            #print("todo ISO level %s\n" % level)
            #cursor.execute( "SET SESSION CHARACTERISTICS AS TRANSACTION " f"ISOLATION LEVEL {level}"
            #cursor.execute("COMMIT")
            #cursor.close()

    def get_isolation_level(self, dbapi_connection):
        if dbapi_connection.autocommit:
            return "AUTOCOMMIT"
        return "SERIALIZABLE"
        #cursor = dbapi_connection.cursor()
        #cursor.execute("show transaction isolation level")
        #val = cursor.fetchone()[0]
        #cursor.close()
        #return val.upper()



