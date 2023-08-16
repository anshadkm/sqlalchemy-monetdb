import pytest
from sqlalchemy.testing.suite import *

# Failures

class TableDDLTest(TableDDLTest):
    @pytest.mark.skip(reason="column names of level >= 3")
    def test_create_table_schema(*args, **kwargs):
        pass


class FutureTableDDLTest(FutureTableDDLTest):
    @pytest.mark.skip(reason="column names of level >= 3")
    def test_create_table_schema(*args, **kwargs):
        pass


class FetchLimitOffsetTest(FetchLimitOffsetTest):
    @pytest.mark.skip(reason="This test does some LIMIT statements in "
                      "the middle of the query, this is not supported.")
    def test_limit_render_multiple_times(*args, **kwargs):
        """
        This test does some LIMIT statements in the middle of the query,
        this is not supported.
        """
        pass


# Errors
@pytest.mark.skip(reason="The tests of this class use self-reference "
                  "foreign keys which are NOT supported by MonetDB")
class CTETest(CTETest):
    pass


@pytest.mark.skip(reason="The dialect is not supporting JSON type")
class JSONTest(JSONTest):
    pass

