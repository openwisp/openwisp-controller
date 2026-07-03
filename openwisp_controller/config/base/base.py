import hashlib
import json
import logging
from copy import deepcopy
from types import SimpleNamespace

from cache_memoize import cache_memoize
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import JSONField
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.utils.functional import cached_property
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from netjsonconfig.exceptions import ValidationError as SchemaError
from swapper import load_model

from openwisp_utils.base import TimeStampedEditableModel

from .. import settings as app_settings

logger = logging.getLogger(__name__)

# Maps the string names used in declarations to the actual Django signals.
_MODEL_SIGNALS = {
    "post_save": post_save,
    "post_delete": post_delete,
    "pre_delete": pre_delete,
    "pre_save": pre_save,
}


def _default_resolve(instance, **kwargs):
    """Default resolver: act on the instance that emitted the signal."""
    return [instance]


def _resolve_pk_snapshot(instance, **kwargs):
    """
    Resolver for delete-triggered dependencies deferred via ``on_commit``.

    Django's ``Collector.delete()`` sets ``instance.pk`` to ``None`` on every
    deleted instance immediately after ``pre_delete``/``post_delete`` signals
    fire, well before an ``on_commit`` callback actually runs. Returning
    ``[instance]`` here would hand the deferred callback a ``None`` pk. This
    returns a disposable object exposing only the pk value, captured now
    while it's still valid.
    """
    return [SimpleNamespace(pk=instance.pk)]


def get_cached_args_rewrite(instance):
    """
    Use only the PK parameter for calculating the cache key
    """
    return instance.pk.hex


class ChecksumCacheMixin:
    """
    Mixin that provides caching for checksum.
    """

    _CHECKSUM_CACHE_TIMEOUT = 60 * 60 * 24 * 30  # 30 days

    @cache_memoize(
        timeout=_CHECKSUM_CACHE_TIMEOUT, args_rewrite=get_cached_args_rewrite
    )
    def get_cached_checksum(self):
        """
        Handles caching,
        timeout=None means value is cached indefinitely
        (invalidation handled on post_save/post_delete signal)
        """
        logger.debug(f"calculating checksum for {self.__class__.__name__} ID {self.pk}")
        return self.checksum

    @classmethod
    def bulk_invalidate_get_cached_checksum(cls, query_params):
        """
        Bulk invalidate checksum cache for multiple instances
        """
        for instance in cls.objects.only("id").filter(**query_params).iterator():
            instance.get_cached_checksum.invalidate(instance)

    def invalidate_checksum_cache(self):
        """
        Invalidate the checksum cache for this instance
        """
        self.get_cached_checksum.invalidate(self)
        logger.debug(
            f"invalidated checksum cache for {self.__class__.__name__} ID {self.pk}"
        )


class ConfigChecksumCacheMixin(ChecksumCacheMixin):
    """
    Mixin that provides caching for both checksum and configuration.
    """

    @cache_memoize(
        timeout=ChecksumCacheMixin._CHECKSUM_CACHE_TIMEOUT,
        args_rewrite=get_cached_args_rewrite,
    )
    def get_cached_configuration(self):
        """
        Returns cached configuration
        """
        return self.generate()

    def invalidate_configuration_cache(self):
        """
        Invalidate the configuration cache for this instance
        """
        self.get_cached_configuration.invalidate(self)
        logger.debug(
            f"invalidated configuration cache for {self.__class__.__name__}"
            f" ID {self.pk}"
        )

    def invalidate_checksum_cache(self):
        super().invalidate_checksum_cache()
        self.invalidate_configuration_cache()


class CacheDependency:
    """
    Declarative description of a related change that must invalidate a cache.

    This is the single, generic mechanism used across the config app to keep
    cached values (configuration checksums, controller view caches, device
    group caches) in sync when a *related* object changes.

    A dependency is wired to a Django signal by :meth:`connect`. When the
    signal fires, :attr:`resolve` returns the objects whose cache must be
    invalidated and :attr:`target` is applied to each of them. ``target`` is
    either the name of a method to call on each resolved object, or a callable
    invoked with the resolved object.

    Parameters
    ----------
    target:
        Either a method name (``str``) invoked on each resolved object, or a
        callable ``target(obj)``. Reusing the existing action methods (e.g.
        ``update_status_if_checksum_changed``, ``invalidate_checksum_cache``)
        and view classmethods keeps behavior identical.
    resolve:
        Callable ``resolve(instance, **signal_kwargs)`` returning an iterable
        of the objects ``target`` must act on. Defaults to acting on the
        instance that emitted the signal (``[instance]``).
    source:
        The signal sender. Either a swappable model label (e.g.
        ``"django_x509.Cert"``) resolved lazily via ``swapper.load_model``, a
        model class, or ``None`` (any sender). Ignored when ``signal_obj`` is a
        custom signal that does not filter by sender.
    signal:
        One of ``post_save``, ``post_delete``, ``pre_delete``, ``pre_save``.
        Ignored when ``signal_obj`` is provided.
    signal_obj:
        A custom Django ``Signal`` instance (e.g. ``config_deactivated``) to
        connect to instead of one of the model signals above.
    track_fields:
        Optional iterable of source field names whose *value* must actually
        change for the dependency to fire. Enabling this registers a
        ``pre_save`` handler that snapshots the old values so the ``post_save``
        handler can compare them, mirroring the manual ``save()`` change
        detection that some models used to perform.
    on_create:
        Whether to act when ``post_save`` reports ``created=True``
        (default ``False``).
    on_commit:
        Whether to defer ``target`` to ``transaction.on_commit``
        (default ``True``, matching the existing handlers).
    """

    _SNAPSHOT_ATTR = "_cache_dependency_snapshots"

    def __init__(
        self,
        *,
        target,
        resolve=_default_resolve,
        source=None,
        signal="post_save",
        signal_obj=None,
        name=None,
        track_fields=None,
        on_create=False,
        on_commit=True,
    ):
        self.target = target
        self.resolve = resolve
        self.source = source
        self.signal_name = signal
        self.signal_obj = signal_obj
        self.name = name
        self.track_fields = list(track_fields) if track_fields else None
        self.on_create = on_create
        self.on_commit = on_commit
        self._uid = None

    @property
    def signal(self):
        if self.signal_obj is not None:
            return self.signal_obj
        return _MODEL_SIGNALS[self.signal_name]

    @property
    def sender(self):
        if isinstance(self.source, str):
            app_label, model_name = self.source.split(".")
            return load_model(app_label, model_name)
        return self.source

    def build_dispatch_uid(self, prefix):
        """
        Builds a descriptive, order-independent ``dispatch_uid``.

        Deriving the uid from the sender, signal and target keeps it stable when
        the surrounding dependency list is reordered and makes it readable in
        tracebacks. ``name`` disambiguates custom signals, which have no natural
        name of their own.
        """
        sender = self.sender
        sender_label = sender._meta.label_lower if sender is not None else "any"
        if self.signal_obj is not None:
            signal_label = self.name or "signal"
        else:
            signal_label = self.signal_name
        target_label = (
            self.target if isinstance(self.target, str) else self.target.__name__
        )
        return f"{prefix}.{sender_label}.{signal_label}.{target_label}"

    def connect(self, dispatch_uid):
        """Connect this dependency's handler to its signal."""
        self._uid = dispatch_uid
        if self.track_fields:
            pre_save.connect(
                self._snapshot_handler,
                sender=self.sender,
                dispatch_uid=f"{dispatch_uid}.snapshot",
                weak=False,
            )
        self.signal.connect(
            self._handler,
            sender=self.sender,
            dispatch_uid=dispatch_uid,
            weak=False,
        )

    def disconnect(self):
        """Disconnect this dependency's handlers (useful for test isolation)."""
        if self._uid is None:
            return
        if self.track_fields:
            pre_save.disconnect(
                sender=self.sender, dispatch_uid=f"{self._uid}.snapshot"
            )
        self.signal.disconnect(sender=self.sender, dispatch_uid=self._uid)

    def _snapshot_handler(self, sender, instance, **kwargs):
        """Store the old values of ``track_fields`` before the instance saves."""
        if instance._state.adding or instance.pk is None:
            return
        fields = self._get_fields_to_track(instance, **kwargs)
        if not fields:
            return
        snapshot, db_fields = self._snapshot_track_fields_from_initial_values(
            instance, fields=fields
        )
        if db_fields:
            db_snapshot = self._snapshot_track_fields_from_db(
                sender, instance, fields=db_fields
            )
            if db_snapshot is None:
                return
            snapshot.update(db_snapshot)
        if snapshot is None:
            return
        snapshots = instance.__dict__.setdefault(self._SNAPSHOT_ATTR, {})
        snapshots[self._uid] = snapshot

    def _get_fields_to_track(self, instance, **kwargs):
        fields = list(self.track_fields or [])
        if not fields:
            return fields
        update_fields = kwargs.get("update_fields")
        # Full save: all tracked fields could have changed.
        if update_fields is None:
            return fields
        # save(update_fields=[...]) narrows the set of potentially changed fields.
        # Expand names to include both field.name and field.attname so a tracked
        # field like ``organization_id`` matches ``organization`` updates.
        expanded = set(update_fields)
        for name in list(update_fields):
            try:
                model_field = instance._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            expanded.add(model_field.name)
            expanded.add(model_field.attname)
        return [field for field in fields if field in expanded]

    def _snapshot_track_fields_from_initial_values(self, instance, fields=None):
        """
        Returns a tuple ``(snapshot, db_fields)`` where ``snapshot`` contains
        values obtained from ``_initial_<field>`` attrs (or ``models.DEFERRED``
        for still deferred fields), while ``db_fields`` contains unresolved
        fields which must be fetched from DB.
        """
        fields = fields or self.track_fields or []
        if not fields:
            return dict(), []
        deferred_fields = instance.get_deferred_fields()
        snapshot = dict()
        db_fields = []
        missing = object()
        for field in fields:
            attr = f"_initial_{field}"
            value = getattr(instance, attr, missing)
            if value is not missing and value != models.DEFERRED:
                snapshot[field] = value
            elif field in deferred_fields:
                snapshot[field] = models.DEFERRED
            else:
                db_fields.append(field)
        return snapshot, db_fields

    def _snapshot_track_fields_from_db(self, sender, instance, fields=None):
        fields = fields or self.track_fields or []
        if not fields:
            return dict()
        try:
            old = sender._default_manager.only(*fields).get(pk=instance.pk)
        except sender.DoesNotExist:
            return None
        return {field: getattr(old, field) for field in fields}

    def _tracked_fields_changed(self, instance):
        snapshots = getattr(instance, self._SNAPSHOT_ATTR, None) or {}
        old = snapshots.get(self._uid)
        if old is None:
            # No snapshot (e.g. on creation) -> nothing to compare against.
            return False
        deferred_fields = instance.get_deferred_fields()
        for field, old_value in old.items():
            if field in deferred_fields:
                continue
            if old_value == models.DEFERRED:
                return True
            if old_value != getattr(instance, field):
                return True
        return False

    def _should_skip(self, instance, **kwargs):
        if (
            self.signal is post_save
            and kwargs.get("created", False)
            and not self.on_create
        ):
            return True
        if self.track_fields and not self._tracked_fields_changed(instance):
            return True
        return False

    def _apply(self, objects):
        for obj in objects:
            if obj is None:
                continue
            if callable(self.target):
                self.target(obj)
            else:
                getattr(obj, self.target)()

    def _handler(self, sender, instance, **kwargs):
        if self._should_skip(instance, **kwargs):
            return
        objects = self.resolve(instance, **kwargs)
        if not objects:
            return
        objects = list(objects)
        if self.on_commit:
            transaction.on_commit(lambda: self._apply(objects))
        else:
            self._apply(objects)


class CacheInvalidationMixin:
    """
    Lets a cache-owning model declare, in one place, which related changes
    invalidate its cached value(s).

    Subclasses override :meth:`get_cache_dependencies` to return a list of
    :class:`CacheDependency`, and ``AppConfig.ready()`` calls
    :meth:`register_cache_dependencies` to wire the Django signals. Adding a new
    related-field dependency is then a matter of appending a declaration,
    instead of scattering ``signal.connect()`` calls across the app.

    The declarations are returned by a classmethod (rather than held in a class
    attribute) so they can reference the model's own private classmethods, which
    do not exist yet while the class body is being evaluated.
    """

    @classmethod
    def get_cache_dependencies(cls):
        """Returns the list of :class:`CacheDependency` for this model."""
        return []

    @classmethod
    def register_cache_dependencies(cls):
        prefix = f"cache_invalidation.{cls._meta.label_lower}"
        for dependency in cls.get_cache_dependencies():
            dependency.connect(dispatch_uid=dependency.build_dispatch_uid(prefix))


class BaseModel(TimeStampedEditableModel):
    """
    Shared logic
    """

    name = models.CharField(max_length=64, db_index=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class BaseConfig(BaseModel):
    """
    Base configuration management model logic shared between models
    """

    backend = models.CharField(
        _("backend"),
        choices=app_settings.BACKENDS,
        max_length=128,
        help_text=_(
            'Select <a href="http://netjsonconfig.openwisp.org/en/'
            'stable/" target="_blank">netjsonconfig</a> backend'
        ),
    )
    config = JSONField(
        _("configuration"),
        default=dict,
        help_text=_("configuration in NetJSON DeviceConfiguration format"),
        encoder=DjangoJSONEncoder,
    )

    __template__ = False
    __vpn__ = False

    class Meta:
        abstract = True

    def clean(self):
        """
        * ensures config is not ``None``
        * performs netjsonconfig backend validation
        """
        if self.config is None:
            self.config = {}
        if not isinstance(self.config, dict):
            raise ValidationError({"config": _("Unexpected configuration format.")})
        # perform validation only if backend is defined, otherwise
        # django will take care of notifying blank field error
        if not self.backend:
            return
        try:
            backend = self.backend_instance
        except ImportError as e:
            message = 'Error while importing "{0}": {1}'.format(self.backend, e)
            raise ValidationError({"backend": message})
        else:
            self.clean_netjsonconfig_backend(backend)

    def get_config(self):
        """
        config preprocessing (skipped for templates):
            * inserts hostname automatically if not present in config
        """
        config = self.config or {}  # might be ``None`` in some corner cases
        if self.__template__:
            return config
        c = deepcopy(config)
        is_config = not any([self.__template__, self.__vpn__])
        if all(("hostname" not in c.get("general", {}), is_config, self.name)):
            c.setdefault("general", {})
            c["general"]["hostname"] = self.name.replace(":", "-")
        return c

    def get_context(self):
        return app_settings.CONTEXT.copy()

    @classmethod
    def validate_netjsonconfig_backend(cls, backend):
        """
        calls ``validate`` method of netjsonconfig backend
        might trigger SchemaError
        """
        # the following line is a trick needed to avoid cluttering
        # an eventual ``ValidationError`` message with ``OrderedDict``
        # which would make the error message hard to read
        backend.config = json.loads(json.dumps(backend.config))
        backend.validate()

    @classmethod
    def clean_netjsonconfig_backend(cls, backend):
        """
        catches any ``SchemaError`` which will be redirected
        to ``django.core.exceptions.ValdiationError``
        """
        try:
            cls.validate_netjsonconfig_backend(backend)
        except SchemaError as e:
            path = [str(el) for el in e.details.path]
            trigger = "/".join(path)
            error = e.details.message
            message = (
                'Invalid configuration triggered by "#/{0}", '
                "validator says:\n\n{1}".format(trigger, error)
            )
            raise ValidationError(message)

    @cached_property
    def backend_class(self):
        """
        returns netjsonconfig backend class
        """
        return import_string(self.backend)

    @cached_property
    def backend_instance(self):
        """
        returns netjsonconfig backend instance
        """
        return self.get_backend_instance()

    def get_backend_instance(self, template_instances=None, context=None, **kwargs):
        """
        allows overriding config and templates
        needed for pre validation of m2m
        """
        backend = self.backend_class
        kwargs.update({"config": self.get_config()})
        context = context or {}
        # determine if we can pass templates
        # expecting a many2many relationship
        if hasattr(self, "templates"):
            if template_instances is None:
                template_instances = self.templates.all()
            templates_list = list()
            for t in template_instances:
                templates_list.append(t.config)
                context.update(t.get_context())
            kwargs["templates"] = templates_list
        # pass context to backend if get_context method is defined
        if hasattr(self, "get_context"):
            context.update(self.get_context())
            kwargs["context"] = context
        backend_instance = backend(**kwargs)
        # remove accidentally duplicated files when combining config and templates
        # this may happen if a device uses multiple VPN client templates
        # which share the same Certification Authority, hence the CA
        # is defined twice, which would raise ValidationError
        if template_instances:
            self._remove_duplicated_files(backend_instance)
        return backend_instance

    @classmethod
    def _remove_duplicated_files(cls, backend_instance):
        if "files" not in backend_instance.config:
            return
        unique_files = []
        for file in backend_instance.config["files"]:
            if file not in unique_files:
                unique_files.append(file)
        backend_instance.config["files"] = unique_files

    def generate(self):
        """
        shortcut for self.backend_instance.generate()
        """
        return self.backend_instance.generate()

    @property
    def checksum(self):
        """
        returns checksum of configuration
        """
        config = self.generate().getvalue()
        return hashlib.md5(config).hexdigest()

    def json(self, dict=False, **kwargs):
        """
        returns JSON representation of object
        """
        config = self.backend_instance.config
        if dict:
            return config
        return json.dumps(config, **kwargs)
