import django
from django.contrib.auth import get_user_model
from django.db import connections
from django.db.utils import DEFAULT_DB_ALIAS
from django.test.testcases import _AssertNumQueriesContext
from django.urls import reverse

from openwisp_users.tests.utils import TestMultitenantAdminMixin

user_model = get_user_model()


class TestAdminMixin(TestMultitenantAdminMixin):
    def _test_changelist_recover_deleted(self, app_label, model_label):
        self._test_multitenant_admin(
            url=reverse('admin:{0}_{1}_changelist'.format(app_label, model_label)),
            visible=[],
            hidden=[],
        )

    def _login(self, username='admin', password='tester'):
        self.client.force_login(user_model.objects.get(username=username))


class _ManagementTransactionNumQueriesContext(_AssertNumQueriesContext):
    def __exit__(self, exc_type, exc_value, traceback):
        """
        Django 4.2 introduced support for logging transaction
        management queries (BEGIN, COMMIT, and ROLLBACK).
        This method increases the number of expected database
        queries if COMMIT/ROLLBACK queries are found when
        using Django 4.2
        """
        if exc_type is not None:
            return
        for query in self.captured_queries:
            if django.VERSION > (4, 2) and 'COMMIT' in query['sql']:
                self.num += 1
        super().__exit__(exc_type, exc_value, traceback)


class TransactionTestMixin(object):
    def assertNumQueries(self, num, func=None, *args, using=DEFAULT_DB_ALIAS, **kwargs):
        conn = connections[using]

        context = _ManagementTransactionNumQueriesContext(self, num, conn)
        if func is None:
            return context

        with context:
            func(*args, **kwargs)
