import inspect
import types


def clone_function_with_globals(func, globals_dict, module_name=None):
    """Clone a function so inherited mixin methods resolve globals in a facade module."""
    cloned = types.FunctionType(
        func.__code__,
        globals_dict,
        name=func.__name__,
        argdefs=func.__defaults__,
        closure=func.__closure__,
    )
    cloned.__kwdefaults__ = getattr(func, "__kwdefaults__", None)
    cloned.__annotations__ = dict(getattr(func, "__annotations__", {}))
    cloned.__doc__ = func.__doc__
    cloned.__module__ = module_name or globals_dict.get("__name__", func.__module__)
    return cloned


def _callable_from_descriptor(raw):
    if isinstance(raw, (staticmethod, classmethod)):
        obj = raw.__func__
    else:
        obj = raw
    return obj if inspect.isfunction(obj) else None


def iter_mixin_callable_names(*mixin_classes, include_inherited=True):
    names = []
    seen = set()
    for mixin_cls in mixin_classes:
        classes = mixin_cls.__mro__ if include_inherited else (mixin_cls,)
        for cls in classes:
            if cls is object:
                continue
            for name, raw in cls.__dict__.items():
                if name.startswith("__") and name != "__init__":
                    continue
                if name in seen:
                    continue
                if _callable_from_descriptor(raw) is None:
                    continue
                seen.add(name)
                names.append(name)
    return names


def rebind_inherited_methods(
    target_cls,
    method_names=None,
    *,
    mixin_classes=None,
    globals_dict=None,
    include_inherited=True,
):
    if method_names is None:
        if mixin_classes is None:
            mixin_classes = [
                base
                for base in target_cls.__mro__[1:]
                if base is not object
            ]
        method_names = iter_mixin_callable_names(
            *mixin_classes,
            include_inherited=include_inherited,
        )
    if globals_dict is None:
        globals_dict = {}
    module_name = globals_dict.get("__name__")

    for name in method_names:
        raw = inspect.getattr_static(target_cls, name, None)
        if raw is None:
            continue
        if isinstance(raw, staticmethod):
            setattr(
                target_cls,
                name,
                staticmethod(
                    clone_function_with_globals(raw.__func__, globals_dict, module_name)
                ),
            )
        elif isinstance(raw, classmethod):
            setattr(
                target_cls,
                name,
                classmethod(
                    clone_function_with_globals(raw.__func__, globals_dict, module_name)
                ),
            )
        elif inspect.isfunction(raw):
            setattr(target_cls, name, clone_function_with_globals(raw, globals_dict, module_name))
    return target_cls
