from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ..tests import TestOrganizationMixin
from .models import OrganizationUser, User


class TestUsers(TestOrganizationMixin, TestCase):
    def _create_user(self, **kwargs):
        opts = dict(username='tester',
                    password='tester',
                    first_name='Tester',
                    last_name='Tester',
                    email='test@tester.com')
        opts.update(kwargs)
        user = User.objects.create_user(**opts)
        return user

    def _create_admin(self, **kwargs):
        opts = dict(username='admin',
                    email='admin@admin.com',
                    is_superuser=True,
                    is_staff=True)
        opts.update(kwargs)
        return self._create_user(**opts)

    def test_create_superuser_email(self):
        user = User.objects.create_superuser(username='tester',
                                             password='tester',
                                             email='test@superuser.com')
        self.assertEqual(user.emailaddress_set.count(), 1)
        self.assertEqual(user.emailaddress_set.first().email, 'test@superuser.com')

    def test_create_superuser_email_empty(self):
        user = User.objects.create_superuser(username='tester',
                                             password='tester',
                                             email='')
        self.assertEqual(user.emailaddress_set.count(), 0)

    def test_admin_add_user_auto_email(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        params = dict(username='testadd',
                      email='test@testadd.com',
                      password1='tester',
                      password2='tester')
        self.client.post(reverse('admin:users_user_add'), params)
        queryset = User.objects.filter(username='testadd')
        self.assertEqual(queryset.count(), 1)
        user = queryset.first()
        self.assertEqual(user.emailaddress_set.count(), 1)
        emailaddress = user.emailaddress_set.first()
        self.assertEqual(emailaddress.email, 'test@testadd.com')
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_change_user_auto_email(self):
        admin = self._create_admin()
        self.client.force_login(admin)
        user = self._create_user(username='changemailtest')
        params = user.__dict__
        params['email'] = 'new@mail.com'
        # inline emails
        params.update({
            'emailaddress_set-TOTAL_FORMS': 1,
            'emailaddress_set-INITIAL_FORMS': 1,
            'emailaddress_set-MIN_NUM_FORMS': 0,
            'emailaddress_set-MAX_NUM_FORMS': 0,
            'emailaddress_set-0-verified': True,
            'emailaddress_set-0-primary': True,
            'emailaddress_set-0-id': user.emailaddress_set.first().id,
            'emailaddress_set-0-user': user.id,
            'users_organizationuser-TOTAL_FORMS': 0,
            'users_organizationuser-INITIAL_FORMS': 0,
            'users_organizationuser-MIN_NUM_FORMS': 0,
            'users_organizationuser-MAX_NUM_FORMS': 0
        })
        response = self.client.post(reverse('admin:users_user_change', args=[user.pk]), params)
        self.assertNotIn('error', str(response.content))
        user = User.objects.get(username='changemailtest')
        email_set = user.emailaddress_set
        self.assertEqual(email_set.count(), 2)
        self.assertEqual(email_set.filter(email='new@mail.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_admin_change_user_email_empty(self):
        admin = self._create_admin(email='')
        self.client.force_login(admin)
        params = dict(username='testchange',
                      email='',
                      first_name='',
                      last_name='',
                      bio='',
                      url='',
                      company='',
                      location='')
        params.update({
            'emailaddress_set-TOTAL_FORMS': 0,
            'emailaddress_set-INITIAL_FORMS': 0,
            'emailaddress_set-MIN_NUM_FORMS': 0,
            'emailaddress_set-MAX_NUM_FORMS': 0,
            'users_organizationuser-TOTAL_FORMS': 0,
            'users_organizationuser-INITIAL_FORMS': 0,
            'users_organizationuser-MIN_NUM_FORMS': 0,
            'users_organizationuser-MAX_NUM_FORMS': 0
        })
        self.client.post(reverse('admin:users_user_change', args=[admin.pk]), params)
        queryset = User.objects.filter(username='testchange')
        self.assertEqual(queryset.count(), 1)
        user = queryset.first()
        self.assertEqual(user.email, '')
        # import pdb; pdb.set_trace()
        self.assertEqual(user.emailaddress_set.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_organizations_pk(self):
        user = self._create_user(username='organizations_pk')
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        self._create_org(name='org3')
        OrganizationUser.objects.create(user=user, organization=org1)
        OrganizationUser.objects.create(user=user, organization=org2)
        self.assertIn((org1.pk,), user.organizations_pk)
        self.assertEqual(len(user.organizations_pk), 2)

    def test_organizations_pk_empty(self):
        user = self._create_user(username='organizations_pk')
        self.assertEqual(len(user.organizations_pk), 0)
