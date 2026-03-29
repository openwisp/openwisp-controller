from django.apps import registry
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.urls.exceptions import NoReverseMatch

from ..utils import SortedOrderedDict

MENU = SortedOrderedDict()


class BaseMenuItem:
    """Base class for all menu items.

    Used to implement common functionality for menu items.
    """

    def __init__(self, config):
        if not isinstance(config, dict):
            raise ImproperlyConfigured(
                f'"config" should be a type of "dict". Error for config- {config}'
            )

    def get_context(self, request=None):
        return self.create_context(request)

    def create_context(self, request=None):
        return {"label": self.label, "url": self.url, "icon": self.icon}

    def set_label(self, config):
        label = config.get("label")
        if not label:
            raise ImproperlyConfigured(f'"label" is missing in the config- {config}')
        self.label = label


class ModelLink(BaseMenuItem):
    """Implements links to model objects.

    Input Parameters: name, model, label, icon.
    """

    def __init__(self, config):
        super().__init__(config)
        name = config.get("name")
        model = config.get("model")
        if name:
            if not isinstance(name, str):
                raise ImproperlyConfigured(
                    f'"name" should be a type of "str". Error for config-{config}'
                )
            self.name = name
        else:
            raise ImproperlyConfigured(f'"name" is missing in the config-{config}')
        if not model:
            raise ImproperlyConfigured(f'"model" is missing in config-{config}')
        if not isinstance(model, str):
            raise ImproperlyConfigured(
                f'"model" should be a type of "str". Error for config-{config}'
            )
        self.model = model
        self.set_label(config)
        self.icon = config.get("icon")
        self.config = config

    def set_label(self, config=None):
        if config.get("label"):
            return super().set_label(config)
        app_label, model = config["model"].split(".")
        model_class = registry.apps.get_model(app_label, model)
        self.label = f"{model_class._meta.verbose_name_plural} {self.name}"

    def create_context(self, request):
        app_label, model = self.model.split(".")
        model_label = model.lower()
        try:
            url = reverse(f"admin:{app_label}_{model_label}_{self.name}")
        except NoReverseMatch:
            raise NoReverseMatch(
                f"Invalid config provided for menu."
                f" No reverse found for the config- {self.config}"
            )
        view_perm = f"{app_label}.view_{model_label}"
        change_perm = f"{app_label}.change_{model_label}"
        user = request.user
        if user.has_perm(view_perm) or user.has_perm(change_perm):
            return {"label": self.label, "url": url, "icon": self.icon}
        return None


class MenuLink(BaseMenuItem):
    """Generic Links.

    Creates a link from a custom url Input parameters: label, url, icon.
    """

    def __init__(self, config):
        super().__init__(config)
        url = config.get("url")
        self.set_label(config)
        if not url:
            raise ImproperlyConfigured(f'"url" is missing in the config- {config}')
        if not isinstance(url, str):
            raise ImproperlyConfigured(
                f'"url" should be a type of "str". Error for the config- {config}'
            )
        self.url = url
        self.icon = config.get("icon")


class MenuGroup(BaseMenuItem):
    """Implements Menu Groups (dropdown).

    Input parameters: label, items and icon. The items is a dict in which
    keys are positions and values must repesent a config for MenuLink or
    ModelLink objects.
    """

    def __init__(self, config):
        super().__init__(config)
        items = config.get("items")
        self.set_label(config)
        if not items:
            raise ImproperlyConfigured(f'"items" is missing in the config- {config}')
        if not isinstance(items, dict):
            raise ImproperlyConfigured(
                f'"items" should be a type of "dict". Error for the config- {config}'
            )
        self.items = SortedOrderedDict()
        self.set_items(items, config)
        self.icon = config.get("icon")

    def get_items(self):
        return self.items

    def set_items(self, items, config):
        _items = {}
        for position, item in items.items():
            if not isinstance(position, int):
                raise ImproperlyConfigured(
                    f'"key" should be type of "int". Error for "items" of config- {config}'
                )

            if not isinstance(item, dict):
                raise ImproperlyConfigured(
                    f'Each value of "items" should be a type of "dict". '
                    f'Error for "items" of config- {config}'
                )
            if item.get("url"):
                # It is a menu link
                try:
                    _items[position] = MenuLink(config=item)
                except ImproperlyConfigured as e:
                    raise ImproperlyConfigured(
                        f'{e}. "items" of config- {config} should have a valid json'
                    )
            elif item.get("model"):
                # It is a model link
                try:
                    _items[position] = ModelLink(config=item)
                except ImproperlyConfigured as e:
                    raise ImproperlyConfigured(
                        f'{e}. "items" of config- {config} should have a valid json'
                    )
            else:
                raise ImproperlyConfigured(
                    f'"items" should have a valid config. Error for config- {config}'
                )
        self.items.update(_items)

    def create_context(self, request):
        _items = []
        for position, item in self.items.items():
            context = item.get_context(request)
            if context:
                context["id"] = position
                _items.append(context)
        if not _items:
            return None
        return {"label": self.label, "sub_items": _items, "icon": self.icon}


def register_menu_group(position, config):
    if not isinstance(position, int):
        raise ImproperlyConfigured('group position should be a type of "int"')
    if not isinstance(config, dict):
        raise ImproperlyConfigured('config should be a type of "dict"')
    if position in MENU:
        item_description = "link"
        if isinstance(MENU[position], MenuGroup):
            item_description = "group"
        label = MENU[position].label
        raise ImproperlyConfigured(
            f'A group/link with config {config} is being registered at position "{position}",\
                but another {item_description} named "{label}" is already registered at the same position.'
        )
    if config.get("url"):
        # It is a menu link
        group_class = MenuLink(config=config)
    elif config.get("items"):
        # It is a menu group
        group_class = MenuGroup(config=config)
    elif config.get("model"):
        # It is a model link
        group_class = ModelLink(config=config)
    else:
        # Unknown
        raise ImproperlyConfigured(f"Invalid config provided at position {position}")
    MENU.update({position: group_class})


def register_menu_subitem(group_position, item_position, config):
    if not isinstance(group_position, int):
        raise ImproperlyConfigured(
            f'Invalid group_position "{group_position}". It should be a type of "int"'
        )
    if not isinstance(item_position, int):
        raise ImproperlyConfigured(
            f'Invalid item_position "{item_position}". It should be a type of "int"'
        )
    if not isinstance(config, dict):
        raise ImproperlyConfigured(
            'Config of sub group item should be a type of "dict"'
        )
    if group_position not in MENU:
        raise ImproperlyConfigured(
            f"A group item with config {config} is being registered in a group\
            which does not exits.",
        )
    group = MENU[group_position]
    if not isinstance(group, MenuGroup):
        raise ImproperlyConfigured(
            f'A group item with config {config} is being registered at group_position\
            "{group_position}" which do not contain any group.',
        )
    if config.get("url"):
        # It is a menu link
        item = MenuLink(config=config)
    elif config.get("model"):
        # It is a model link
        item = ModelLink(config=config)
    else:
        # Unknown
        raise ImproperlyConfigured(
            f'Invalid config "{config}" provided for sub group item'
        )
    if item_position in group.items:
        name = group.items[item_position]
        raise ImproperlyConfigured(
            f'A group item with config {config} is being registered at position\
            "{item_position}" in a group but another item named "{name}" is already registered\
            at the same position.'
        )
    group.items.update({item_position: item})


def build_menu_groups(request):
    menu = []
    for position, item in MENU.items():
        item_context = item.get_context(request)
        if item_context:
            item_context["id"] = position
            menu.append(item_context)
    return menu
