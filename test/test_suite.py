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

class IdentityColumnTest(IdentityColumnTest):

    @pytest.mark.skip(reason="This test names a table column 'desc' "
                      "which collides with the SQL Standard DESC keyword")
    def test_insert_always_error(self, connection):
        pass

    @pytest.mark.skip(reason="This test names a table column 'desc' "
                      "which collides with the SQL Standard DESC keyword")
    def test_select_all(self, connection):
        pass

    @pytest.mark.skip(reason="This test names a table column 'desc' "
                      "which collides with the SQL Standard DESC keyword")
    def test_select_columns(self, connection):
        pass


class IdentityAutoincrementTest(IdentityAutoincrementTest):

    @pytest.mark.skip(reason="This test names a table column 'desc' "
                      "which collides with the SQL Standard DESC keyword")
    def test_autoincrement_with_identity(self, connection):
        pass


@pytest.mark.skip(reason="The tests of this class use self-reference "
                  "foreign keys which are NOT supported by MonetDB")
class CTETest(CTETest):
    pass


#@pytest.mark.skip(reason="The tests of this class use the CHECK column "
#                  "constraint which is not support by MonetDB. The "
#                  "expression compiler gives a Warning so the user is "
#                  "notified for the skipped constraint but Warning are "
#                  "turned to exceptions from the test suite")
#class QuotedNameArgumentTest(QuotedNameArgumentTest):
#    pass


@pytest.mark.skip(reason="The dialect is not supporting JSON type")
class JSONTest(JSONTest):
    pass

