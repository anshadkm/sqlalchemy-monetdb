from typing import Optional
from typing import TYPE_CHECKING
from typing import overload

from sqlalchemy.sql import sqltypes as sqltypes
from sqlalchemy.types import INTEGER, BIGINT, SMALLINT, VARCHAR, CHAR, TEXT,\
    FLOAT, DATE, BOOLEAN, DECIMAL, TIMESTAMP, BLOB, UUID
from uuid import UUID as _python_UUID

class INET(sqltypes.TypeEngine):
    __visit_name__ = "INET"


class URL(sqltypes.TypeEngine):
    __visit_name__ = "URL"


class WRD(sqltypes.Integer):
    __visit_name__ = "WRD"


class DOUBLE_PRECISION(sqltypes.Float):
    __visit_name__ = 'DOUBLE PRECISION'


class TINYINT(sqltypes.Integer):
    __visit_name__ = "TINYINT"

class TIME(sqltypes.TIME):
    """MonetDB TIME type."""

    __visit_name__ = "TIME"

    def __init__(
        self, timezone: bool = False, precision: Optional[int] = None
    ) -> None:
        """Construct a TIME.

        :param timezone: boolean value if timezone present, default False
        :param precision: optional integer precision value

         .. versionadded:: 2.0

        """
        super().__init__(timezone=timezone)
        self.precision = precision
        print('time self', precision)


class MDB_UUID(sqltypes.UUID[sqltypes._UUID_RETURN]):
    render_bind_cast = True
    render_literal_cast = True

    if TYPE_CHECKING:

        @overload
        def __init__(
            self: MDB_UUID[_python_UUID], as_uuid: Literal[True] = ...
        ) -> None:
            ...

        @overload
        def __init__(self: MDB_UUID[str], as_uuid: Literal[False] = ...) -> None:
            ...

        def __init__(self, as_uuid: bool = True) -> None:
            ...


MONETDB_TYPE_MAP = {
    'tinyint': TINYINT,
    'wrd': WRD,
    'url': URL,
    'inet': INET,
    'bigint': BIGINT,
    'blob': BLOB,
    'boolean': BOOLEAN,
    'char': CHAR,
    'clob': TEXT,
    'date': DATE,
    'decimal': DECIMAL,
    'double': DOUBLE_PRECISION,
    'int': INTEGER,
    'real': FLOAT,
    'smallint': SMALLINT,
    'time': TIME,
    'timetz': TIME,
    'timestamp': TIMESTAMP,
    'timestamptz': TIMESTAMP,
    'varchar': VARCHAR,
    'uuid': UUID,
}
