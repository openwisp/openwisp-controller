import json
from types import SimpleNamespace

from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.utils.translation import gettext_lazy as _
from swapper import load_model

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

    # Every connected dependency (model-owned or app-level) registers itself
    # here, keyed by its dispatch_uid, so the whole invalidation graph can be
    # introspected at runtime (see ``get_registered_dependencies`` and the
    # ``print_cache_dependencies`` management command).
    _registry = {}

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
        name of their own. The resolver, tracked fields and timing are also
        encoded so two dependencies that share sender/signal/target but differ
        in those attributes cannot collide and silently overwrite each other in
        ``CacheDependency._registry``.
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
        resolve_label = (
            "instance" if self.resolve is _default_resolve else self.resolve.__name__
        )
        parts = [prefix, sender_label, signal_label, target_label, resolve_label]
        if self.track_fields:
            parts.append("+".join(self.track_fields))
        if self.on_create:
            parts.append("oncreate")
        if not self.on_commit:
            parts.append("immediate")
        return ".".join(parts)

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
        CacheDependency._registry[dispatch_uid] = self

    def disconnect(self):
        """Disconnect this dependency's handlers (useful for test isolation)."""
        if self._uid is None:
            return
        if self.track_fields:
            pre_save.disconnect(
                sender=self.sender, dispatch_uid=f"{self._uid}.snapshot"
            )
        self.signal.disconnect(sender=self.sender, dispatch_uid=self._uid)
        CacheDependency._registry.pop(self._uid, None)

    @classmethod
    def get_registered_dependencies(cls):
        """Returns all connected dependencies, sorted by ``dispatch_uid``."""
        return [cls._registry[uid] for uid in sorted(cls._registry)]

    def describe(self):
        """Returns a plain dict describing this dependency for introspection."""
        sender = self.sender
        if self.signal_obj is not None:
            signal = self.name or "custom"
        else:
            signal = self.signal_name
        target = (
            self.target if isinstance(self.target, str) else self.target.__qualname__
        )
        if self.resolve is _default_resolve:
            resolve = "instance"
        else:
            resolve = self.resolve.__name__
        return {
            "source": sender._meta.label_lower if sender is not None else "any",
            "signal": signal,
            "target": target,
            "resolve": resolve,
            "track_fields": self.track_fields,
            "on_create": self.on_create,
            "on_commit": self.on_commit,
            "dispatch_uid": self._uid,
        }

    @classmethod
    def render_registered(cls, fmt="text"):
        """
        Returns a string describing every connected cache dependency.

        ``fmt`` is either ``"text"`` (human-readable, grouped by source and
        signal) or ``"json"`` (a machine-readable list of ``describe()`` dicts).
        """
        dependencies = cls.get_registered_dependencies()
        if fmt == "json":
            return json.dumps([dep.describe() for dep in dependencies], indent=2)
        if not dependencies:
            return _("No cache dependencies are registered.")
        lines = []
        last_group = None
        for dep in dependencies:
            info = dep.describe()
            group = (info["source"], info["signal"])
            if group != last_group:
                if last_group is not None:
                    lines.append("")
                lines.append("{0} ({1})".format(info["source"], info["signal"]))
                last_group = group
            lines.append("  " + _("target: {target}").format(target=info["target"]))
            details = "    " + _("resolve: {resolve}").format(resolve=info["resolve"])
            if info["track_fields"]:
                details += _("   track_fields: {fields}").format(
                    fields=", ".join(info["track_fields"])
                )
            details += _("   on_create: {on_create}   on_commit: {on_commit}").format(
                on_create=info["on_create"], on_commit=info["on_commit"]
            )
            lines.append(details)
            lines.append("    " + _("uid: {uid}").format(uid=info["dispatch_uid"]))
        return "\n".join(lines)

    def _snapshot_handler(self, sender, instance, **kwargs):
        """Store the old values of ``track_fields`` before the instance saves."""
        if instance._state.adding or instance.pk is None:
            return
        if not self._may_track_fields_change(instance, **kwargs):
            # A previous save may have left a snapshot on this instance; drop it
            # so it cannot bleed into this save(update_fields=...) comparison.
            self._discard_snapshot(instance)
            return
        snapshot = self._snapshot_from_initial_values(instance)
        if snapshot is None:
            snapshot = self._snapshot_from_db(sender, instance)
            if snapshot is None:
                self._discard_snapshot(instance)
                return
        snapshots = instance.__dict__.setdefault(self._SNAPSHOT_ATTR, {})
        snapshots[self._uid] = snapshot

    def _discard_snapshot(self, instance):
        """Remove this dependency's stored snapshot from ``instance`` if any."""
        snapshots = getattr(instance, self._SNAPSHOT_ATTR, None)
        if snapshots is not None:
            snapshots.pop(self._uid, None)

    def _may_track_fields_change(self, instance, **kwargs):
        """
        ``save(update_fields=[...])`` guarantees only those fields are
        persisted; if none of them are ``track_fields``, nothing we care
        about could have changed, so skip snapshotting (and the DB fetch
        it may trigger) entirely.
        """
        update_fields = kwargs.get("update_fields")
        if update_fields is None:
            return True
        expanded = set(update_fields)
        for name in update_fields:
            try:
                model_field = instance._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            expanded.add(model_field.name)
            expanded.add(model_field.attname)
        return any(field in expanded for field in self.track_fields)

    def _snapshot_from_initial_values(self, instance):
        """
        Builds the snapshot from ``_initial_<field>`` attributes already set
        by the model (e.g. ``Device._set_initial_values_for_changed_checked_fields``),
        avoiding a DB round-trip. Returns ``None`` if any tracked field lacks
        one, so the caller falls back to fetching the old values from the DB.
        """
        missing = object()
        snapshot = dict()
        for field in self.track_fields:
            value = getattr(instance, f"_initial_{field}", missing)
            if value is missing:
                return None
            snapshot[field] = value
        return snapshot

    def _snapshot_from_db(self, sender, instance):
        try:
            old = sender._default_manager.only(*self.track_fields).get(pk=instance.pk)
        except sender.DoesNotExist:
            return None
        return {field: getattr(old, field) for field in self.track_fields}

    def _tracked_fields_changed(self, instance):
        snapshots = getattr(instance, self._SNAPSHOT_ATTR, None) or {}
        # Consume the snapshot: a reused instance saved again (e.g. with
        # ``update_fields``) must not compare against this stale snapshot.
        old = snapshots.pop(self._uid, None)
        if old is None:
            # No snapshot (e.g. on creation) -> nothing to compare against.
            return False
        for field, old_value in old.items():
            if old_value is models.DEFERRED:
                # Old value unknown (was deferred at snapshot time); assume changed.
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
