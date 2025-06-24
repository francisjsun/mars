import typing

T = typing.TypeVar("T")
SmartList = typing.Union[None, T, list[T]]
StrList = SmartList[str]


def get_list(param_list) -> list:
    if param_list is None:
        return []
    elif not isinstance(param_list, list):
        return [param_list]
    else:
        return param_list
