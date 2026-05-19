from abc import ABC, abstractmethod
from collections.abc import Callable

from ucap.config import Var


class BaseProbe(ABC):

    def __init__(self, serial_no: str = ''):
        self._serial_no = serial_no

    @abstractmethod
    def get_func_args(self, var: Var) -> tuple[Callable, list]:
        ...

    def get_serial_no(self) -> str:
        return self._serial_no

    def close(self) -> None:
        pass
