# modules/sbp_root.py
import os
from pathlib import Path
from typing import Dict, Optional, Union


class SBPPath:
    """
    Вспомогательный класс для построения цепочек путей.
    
    Поддерживает бесконечные цепочки через оператор /.
    """
    
    def __init__(self, root: 'SBPRoot', path: str):
        self._root = root
        self._path = path
    
    def __truediv__(self, other: str) -> 'SBPPath':
        """Продолжение цепочки: path / "subdir" """
        if other in self._root._roots:
            return SBPPath(self._root, self._root._roots[other])
        return SBPPath(self._root, os.path.join(self._path, other))
    
    def __rtruediv__(self, other: str) -> 'SBPPath':
        """Обратная цепочка: "base" / path """
        return SBPPath(self._root, os.path.join(other, self._path))
    
    def __str__(self) -> str:
        return self._path
    
    def __repr__(self) -> str:
        return f"SBPPath('{self._path}')"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self._path == other
        if isinstance(other, SBPPath):
            return self._path == other._path
        return False
    
    def __add__(self, other: str) -> str:
        return self._path + other
    
    def __radd__(self, other: str) -> str:
        return other + self._path
    
    def path(self, *args) -> str:
        """Добавляет части к пути."""
        if args:
            return os.path.join(self._path, *args)
        return self._path
    
    def pathlib(self, *args) -> Path:
        """Возвращает Path объект."""
        return Path(self.path(*args))
    
    def exists(self) -> bool:
        return Path(self._path).exists()
    
    def is_dir(self) -> bool:
        return Path(self._path).is_dir()
    
    def is_file(self) -> bool:
        return Path(self._path).is_file()
    
    def mkdir(self, parents: bool = True, exist_ok: bool = True) -> None:
        Path(self._path).mkdir(parents=parents, exist_ok=exist_ok)
    
    def glob(self, pattern: str):
        return Path(self._path).glob(pattern)
    
    def rglob(self, pattern: str):
        return Path(self._path).rglob(pattern)
    
    def parent(self) -> 'SBPPath':
        return SBPPath(self._root, str(Path(self._path).parent))
    
    def name(self) -> str:
        return Path(self._path).name
    
    def stem(self) -> str:
        return Path(self._path).stem
    
    def suffix(self) -> str:
        return Path(self._path).suffix
    
    @property
    def as_posix(self) -> str:
        return Path(self._path).as_posix()
    
    def __lt__(self, other) -> bool:
        return self._path < str(other)
    
    def __le__(self, other) -> bool:
        return self._path <= str(other)
    
    def __gt__(self, other) -> bool:
        return self._path > str(other)
    
    def __ge__(self, other) -> bool:
        return self._path >= str(other)
    
    def __hash__(self) -> int:
        return hash(self._path)


class SBPRoot:
    """
    Умный менеджер путей для мультибанковской системы.
    
    Поддерживает:
    - Словарный синтаксис: SBP_ROOT["ci"] → "/sbp/ci"
    - Строковый синтаксис: str(SBP_ROOT) → "/sbp/ci"
    - Pathlib-цепочки: SBP_ROOT / "sb" / "zkh_ursv" / "base" → "/sbp/sb/zkh_ursv/base"
    - Автоматическое распознавание банков в цепочках
    - Полную обратную совместимость
    """
    
    def __init__(self, root_path: str, default_bank: str = "ci"):
        self._root_path = root_path
        self._default_bank = default_bank
        self._roots: Dict[str, str] = {}
        self._current_path: Optional[str] = None
    
    def add_bank(self, bank: str, subdir: str) -> None:
        """Добавляет банк в словарь."""
        self._roots[bank] = os.path.join(self._root_path, subdir)
    
    def __getitem__(self, key: str) -> str:
        """Поддержка словарного синтаксиса: SBP_ROOT["ci"]"""
        if key not in self._roots:
            raise KeyError(f"Банк '{key}' не найден. Доступные: {list(self._roots.keys())}")
        return self._roots[key]
    
    def __str__(self) -> str:
        """Поддержка строкового синтаксиса: str(SBP_ROOT)"""
        if self._current_path is not None:
            return self._current_path
        return self._roots.get(self._default_bank, self._root_path)
    
    def __repr__(self) -> str:
        return f"SBPRoot(default='{self._default_bank}', roots={self._roots})"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, SBPPath):
            return str(self) == str(other)
        return False
    
    def __truediv__(self, other: str) -> Union[SBPPath, str]:
        """Поддержка pathlib: SBP_ROOT / "sb" / "zkh_ursv" """
        if other in self._roots:
            return SBPPath(self, self._roots[other])
        base_path = self._roots.get(self._default_bank, self._root_path)
        return SBPPath(self, os.path.join(base_path, other))
    
    def __rtruediv__(self, other: str) -> SBPPath:
        """Поддержка pathlib: "base" / SBP_ROOT """
        return SBPPath(self, os.path.join(other, str(self)))
    
    def __add__(self, other: str) -> str:
        return str(self) + other
    
    def __radd__(self, other: str) -> str:
        return other + str(self)
    
    def __contains__(self, key: str) -> bool:
        return key in self._roots
    
    def __iter__(self):
        return iter(self._roots)
    
    def __len__(self) -> int:
        return len(self._roots)
    
    def get(self, key: str, default: Optional[str] = None) -> str:
        if default is None:
            default = self._roots.get(self._default_bank, self._root_path)
        return self._roots.get(key, default)
    
    def path(self, *args) -> str:
        """Построение пути: SBP_ROOT.path('sb', 'zkh_ursv', 'base')"""
        if not args:
            return str(self)
        first = args[0]
        if first in self._roots:
            base = self._roots[first]
            rest = args[1:]
        else:
            base = str(self)
            rest = args
        if rest:
            return os.path.join(base, *rest)
        return base
    
    def pathlib(self, *args) -> Path:
        """Возвращает Path объект."""
        return Path(self.path(*args))
    
    def join(self, *args) -> str:
        """Синоним для path()."""
        return self.path(*args)
    
    def keys(self):
        return self._roots.keys()
    
    def values(self):
        return self._roots.values()
    
    def items(self):
        return self._roots.items()
    
    def get_banks(self) -> list:
        return list(self._roots.keys())
    
    def get_paths(self) -> dict:
        return dict(self._roots)
    
    def bank_path(self, bank: str, *args) -> str:
        root = self._roots.get(bank, self._roots.get(self._default_bank, self._root_path))
        if args:
            return os.path.join(root, *args)
        return root
    
    def bank_pathlib(self, bank: str, *args) -> Path:
        return Path(self.bank_path(bank, *args))
    
    @property
    def default(self) -> str:
        return self._roots.get(self._default_bank, self._root_path)
    
    @property
    def default_bank(self) -> str:
        return self._default_bank
    
    @property
    def root_path(self) -> str:
        return self._root_path
    
    def set_default(self, bank: str) -> None:
        if bank in self._roots:
            self._default_bank = bank
    
    def to_dict(self) -> Dict[str, str]:
        return dict(self._roots)
    
    def exists(self, *args) -> bool:
        return Path(self.path(*args)).exists()
    
    def is_dir(self, *args) -> bool:
        return Path(self.path(*args)).is_dir()
    
    def is_file(self, *args) -> bool:
        return Path(self.path(*args)).is_file()
    
    def mkdir(self, *args, parents: bool = True, exist_ok: bool = True) -> None:
        Path(self.path(*args)).mkdir(parents=parents, exist_ok=exist_ok)
    
    def glob(self, pattern: str, *args):
        return Path(self.path(*args)).glob(pattern)
    
    def rglob(self, pattern: str, *args):
        return Path(self.path(*args)).rglob(pattern)


def create_sbp_root(root_path: str, default_bank: str = "ci") -> SBPRoot:
    """Создаёт объект SBPRoot с банками по умолчанию."""
    sbp_root = SBPRoot(root_path, default_bank)
    sbp_root.add_bank("ci", "ci")
    sbp_root.add_bank("sb", "sb")
    sbp_root.add_bank("vtb", "vtb")
    return sbp_root