from django.utils.text import slugify
from django_loci.tests import TestLociMixin
from swapper import load_model

Organization = load_model('openwisp_users', 'Organization')


class TestGeoMixin(TestLociMixin):
    def _create_organization(self, **kwargs):
        options = dict(name='org1')
        options.update(kwargs)
        options.setdefault('slug', slugify(options['name']))
        if not Organization.objects.filter(**kwargs).count():
            org = Organization(**options)
            org.full_clean()
            org.save()
        else:
            org = Organization.objects.get(**kwargs)
        return org

    def _add_default_org(self, kwargs):
        if 'organization' not in kwargs:
            kwargs['organization'] = self._create_organization()
        return kwargs

    def _create_object(self, **kwargs):
        if 'location' in kwargs:
            kwargs['organization'] = kwargs['location'].organization
        if 'location' not in kwargs:
            kwargs['hardware_id'] = '1234'
        self._add_default_org(kwargs)
        return super()._create_object(**kwargs)

    def _create_location(self, **kwargs):
        self._add_default_org(kwargs)
        return super()._create_location(**kwargs)

    def _create_floorplan(self, **kwargs):
        if 'location' not in kwargs:
            kwargs['location'] = self._create_location(type='indoor')
        kwargs['organization'] = kwargs['location'].organization
        return super()._create_floorplan(**kwargs)

    def _create_object_location(self, **kwargs):
        if 'location' not in kwargs:
            kwargs['location'] = self._create_location()
        kwargs['organization'] = kwargs['location'].organization
        if 'content_object' not in kwargs:
            kwargs['content_object'] = self._create_object(
                organization=kwargs['organization']
            )
        if kwargs['location'].type == 'indoor':
            kwargs['indoor'] = '-140.38620,40.369227'
        del kwargs['organization']  # not needed in this model
        ol = self.object_location_model(**kwargs)
        ol.full_clean()
        ol.save()
        return ol
