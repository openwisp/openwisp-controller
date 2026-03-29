from collections.abc import Sequence

from django.utils.functional import Promise


class memoized_lazy_function(Promise):
    """
    Represents a lazy value which is calculated by calling
    func(*args, **kwargs) and then is memoized.

    >>> f = memoized_lazy_function(lambda a: print('.') or a, 'hello')
    >>> f()
    .
    'hello'
    >>> f()
    'hello'
    """

    def __init__(self, func, *args, **kwargs):
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __call__(self):
        if not hasattr(self, '_result'):
            self._result = self._func(*self._args, **self._kwargs)
        return self._result


class ListWithLazyItems(Sequence):
    """
    Mimics a lazy list.

    It keeps items in lazy state and evaluates them when they're
    returned.

    An item is considered lazy when it is
    a `django.utils.functional.Promise` instance.
    """

    def __init__(self, iterable=()):
        if isinstance(iterable, ListWithLazyItems):
            iterable = iterable._list
        self._list = list(iterable)

    def __iter__(self):
        for item in self._list:
            yield self._resolve_lazy_item(item)

    def __len__(self):
        return len(self._list)

    def __getitem__(self, index):
        return self._resolve_lazy_item(self._list[index])

    def extend(self, iterable):
        if isinstance(iterable, ListWithLazyItems):
            iterable = iterable._list
        self._list.extend(iterable)

    def __radd__(self, iterable):
        lazy_list = type(self)(iterable)  # copy
        lazy_list.extend(self)
        return lazy_list

    def __add__(self, iterable):
        lazy_list = type(self)(self)  # copy
        lazy_list.extend(iterable)
        return lazy_list

    @classmethod
    def _resolve_lazy_item(cls, item):
        if cls.is_lazy_item(item):
            item = item()

        return item

    @classmethod
    def is_lazy_item(cls, item):
        return isinstance(item, Promise)


class ListWithLazyItemsRawIterator(ListWithLazyItems):
    """
    This lazy list yields raw items (i.e. Promises are not resolved)
    when iterated.
    """

    def __iter__(self):
        return iter(self._list)
