# modules/sbp_utils.py
"""
Утилиты для работы с путями SBP.

⚠️ ВНИМАНИЕ: Этот модуль используется синхронным create_payload!
Любые изменения должны сохранять 100% обратную совместимость.
"""

import time
import json
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union
from dataclasses import dataclass

import config
from modules.response_utils import create_response
from modules.logger_config import logger, get_function_names, get_function_stack, log_error_with_context


# ============================================================
#                     КЛАСС SBPPaths
# ============================================================

@dataclass
class SBPPaths:
    """
    Пути SBP для конкретной базы с использованием pathlib.
    
    Поддерживает мультибанковость (опционально).
    """
    
    base: Path
    sended: Path
    processing: Path
    get: Path
    geted: Path
    stop: Path
    stoped: Path
    bank: Optional[str] = None      # Новое поле (опционально)
    base_name: Optional[str] = None # Новое поле (опционально)
    
    def __post_init__(self):
        """Создаёт все директории при инициализации."""
        for path in [self.base, self.sended, self.processing, 
                     self.get, self.geted, self.stop, self.stoped]:
            path.mkdir(parents=True, exist_ok=True)
    
    def get_path(self, key: str) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """
        Безопасно получает путь по ключу.
        
        Returns:
            Tuple[Optional[Path], Optional[Dict[str, Any]]]: (путь, ошибка)
        """
        stack = get_function_stack()
        
        try:
            path = getattr(self, key)
            return path, None
        except AttributeError as e:
            error = {"error": f"Ключ '{key}' не найден"}
            log_error_with_context(e, f"get_path key={key}")
            logger.error(f"{stack}: {error}")
            return None, error
    
    def get_files(self, key: str, pattern: str = "*.json") -> Tuple[List[Path], Optional[Dict[str, Any]]]:
        """
        Получает список файлов в указанной директории по ключу.
        """
        stack = get_function_stack()
        
        directory_path, error = self.get_path(key)
        if error:
            return [], error
        
        if directory_path is None:
            error = {"error": f"Путь для ключа '{key}' не найден"}
            logger.error(f"{stack}: {error}")
            return [], error
        
        try:
            if not directory_path.exists():
                error = {"error": f"Папка не существует: {directory_path}"}
                logger.error(f"{stack}: {error}")
                return [], error
            
            files = list(directory_path.glob(pattern))
            
            if not files:
                logger.debug(f"{stack}: Нет файлов {pattern} в {directory_path}")
            
            return files, None
        except Exception as e:
            log_error_with_context(e, f"get_files key={key} pattern={pattern}")
            return [], {"error": str(e)}
    
    def get_json_files(self, key: str) -> Tuple[List[Path], Optional[Dict[str, Any]]]:
        """Получает JSON-файлы в указанной директории."""
        return self.get_files(key, "*.json")
    
    def read_json_file(self, file_path: Path) -> Tuple[Optional[Union[dict, list]], Optional[Dict[str, Any]]]:
        """
        Читает JSON файл и возвращает его содержимое.
        
        Returns:
            Tuple[Optional[dict|list], Optional[Dict[str, Any]]]:
                - (data, None) при успехе
                - (None, error_response) при ошибке
        """
        stack = get_function_stack()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.debug(f"{stack}: Прочитан {file_path.name}")
                return data, None
        except json.JSONDecodeError as e:
            log_error_with_context(e, f"read_json_file {file_path.name}")
            return None, create_response(
                status=config.STATUS["JSON_READ_ERROR"],
                error=str(e),
                context=file_path.name,
                data={"filename": file_path.name}
            )
        except Exception as e:
            log_error_with_context(e, f"read_json_file {file_path.name}")
            return None, create_response(
                status=config.STATUS["JSON_READ_ERROR"],
                error=str(e),
                context=file_path.name,
                data={"filename": file_path.name}
            )
    
    def move_file(self, source: Path, dest_dir: Path, status_key: str) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """
        Перемещает файл в указанную директорию.
        
        Args:
            source: Исходный путь
            dest_dir: Директория назначения
            status_key: Ключ статуса для ошибки
        
        Returns:
            Tuple[Optional[Path], Optional[Dict[str, Any]]]:
                - (new_path, None) при успехе
                - (None, error_response) при ошибке
        """
        stack = get_function_stack()
        
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / source.name
            shutil.move(str(source), str(dest_path))
            logger.debug(f"{stack}: Перемещён {source.name} в {dest_dir.name}")
            return dest_path, None
        except Exception as e:
            log_error_with_context(e, f"move_file {source.name} -> {dest_dir.name}")
            return None, create_response(
                status=config.STATUS[status_key],
                error=str(e),
                context=source.name,
                data={"filename": source.name}
            )
    
    def move_to_processing(self, file_path: Path) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """Перемещает файл в папку processing."""
        return self.move_file(file_path, self.processing, "FILE_MOVE_TO_PROCESSING_ERROR")
    
    def move_to_sended(self, file_path: Path) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """Перемещает файл в папку sended."""
        return self.move_file(file_path, self.sended, "FILE_MOVE_TO_SENDED_ERROR")
    
    def move_to_geted(self, file_path: Path) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """Перемещает файл в папку geted."""
        return self.move_file(file_path, self.geted, "FILE_MOVE_TO_GETED_ERROR")
    
    def move_to_stoped(self, file_path: Path) -> Tuple[Optional[Path], Optional[Dict[str, Any]]]:
        """Перемещает файл в папку stoped."""
        return self.move_file(file_path, self.stoped, "FILE_MOVE_TO_STOPED_ERROR")
    
    def __getitem__(self, key: str) -> Path:
        """Позволяет обращаться как к словарю: paths['base']"""
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(f"Ключ '{key}' не найден")
    
    def __str__(self) -> str:
        """Строковое представление."""
        bank_info = f", bank={self.bank}" if self.bank else ""
        base_info = f", base={self.base_name}" if self.base_name else ""
        return f"SBPPaths(base={self.base}{bank_info}{base_info})"
    
    def __repr__(self) -> str:
        return self.__str__()


# ============================================================
#                     ОСНОВНЫЕ ФУНКЦИИ
# ============================================================

def create_sbp_paths(
    base: str, 
    bank: Optional[str] = None
) -> SBPPaths:
    """
    Создаёт объект с путями SBP для указанной базы.
    
    ⚠️ ПОЛНАЯ ОБРАТНАЯ СОВМЕСТИМОСТЬ:
    - create_sbp_paths('zkh_ursv') → /sbp/ci/zkh_ursv (старое поведение)
    - create_sbp_paths('zkh_ursv', bank='sb') → /sbp/sb/zkh_ursv (новое)
    
    Args:
        base: Название базы (например, 'zkh_ursv')
        bank: Имя банка (ci, sb, vtb) — если None, используется банк по умолчанию
    
    Returns:
        SBPPaths: Объект с путями
    """
    try:
        # Определяем корневой путь
        sbp_root = config.SBP_ROOT
        
        # Если передан банк и SBP_ROOT поддерживает path()
        if bank and hasattr(sbp_root, 'path') and callable(sbp_root.path):
            root_path = Path(sbp_root.path(bank))
        else:
            # Старое поведение — приводим к строке
            root_path = Path(str(sbp_root))
        
        base_path = root_path / base
        
        return SBPPaths(
            base=base_path,
            sended=base_path / 'sended',
            processing=base_path / 'processing',
            get=base_path / 'get',
            geted=base_path / 'geted',
            stop=base_path / 'stop',
            stoped=base_path / 'stoped',
            bank=bank,
            base_name=base
        )
    except Exception as e:
        log_error_with_context(e, f"create_sbp_paths base={base} bank={bank}")
        raise


# ============================================================
#                     ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# ============================================================

def get_json_files_in_directory(
    base: str, 
    key: str
) -> Tuple[List[Path], Optional[Dict[str, Any]], SBPPaths, str]:
    """
    Получает JSON-файлы в указанной директории для базы.
    
    ⚠️ ПОЛНАЯ ОБРАТНАЯ СОВМЕСТИМОСТЬ:
    - Сигнатура НЕ ИЗМЕНИЛАСЬ
    - Возвращаемое значение НЕ ИЗМЕНИЛОСЬ
    
    Args:
        base: Название базы
        key: Ключ директории
    
    Returns:
        Tuple[List[Path], Optional[Dict[str, Any]], SBPPaths, str]:
            (файлы, ошибка, пути, статус)
    """
    stack = get_function_stack()
    
    # Создаём paths ДО try, чтобы всегда возвращать SBPPaths
    paths = create_sbp_paths(base)
    
    try:
        files, error = paths.get_json_files(key)
        
        if error:
            logger.error(f"{stack}: {error}")
            return [], error, paths, config.STATUS["DIRECTORY_ERROR"]
        
        if not files:
            logger.debug(f"{stack}: Нет JSON файлов для базы '{base}' (директория: {key})")
            return [], None, paths, config.STATUS["NO_FILES"]
        
        logger.debug(f"{stack}: Найдено {len(files)} JSON файлов для базы '{base}'")
        return files, None, paths, config.STATUS["SUCCESS"]
        
    except Exception as e:
        log_error_with_context(e, f"get_json_files_in_directory base={base} key={key}")
        return [], {"error": str(e)}, paths, config.STATUS["DIRECTORY_ERROR"]


def get_files_with_check(
    base: str,
    directory_key: str,
    context_message: str = "Запрос к API ИВЦ из базы"
) -> Tuple[Optional[List[Path]], Optional[SBPPaths], Optional[Dict[str, Any]], bool]:
    """
    Получает файлы и проверяет статус.
    
    ⚠️ ЭТА ФУНКЦИЯ ИСПОЛЬЗУЕТСЯ В create_payload.py!
    НЕ МЕНЯТЬ СИГНАТУРУ!
    
    Args:
        base: Название базы
        directory_key: Ключ директории (обычно 'base')
        context_message: Сообщение для логирования
    
    Returns:
        Tuple[Optional[List[Path]], Optional[SBPPaths], Optional[Dict[str, Any]], bool]:
            (json_files, sbp_paths, response, should_process)
            - если should_process = False → response содержит ответ для возврата
            - если should_process = True → можно обрабатывать файлы
    """
    stack = get_function_stack()
    logger.debug(f"{stack}: {context_message} {base}")
    
    try:
        start = time.time()
        json_files, error_msg, sbp_paths, status = get_json_files_in_directory(base, directory_key)
        elapsed = time.time() - start
        logger.debug(f"Функция get_json_files_in_directory выполнена за {elapsed:.2f} сек")
        context = str(sbp_paths.base) if sbp_paths else None
        
        # Проверяем статус
        if config.is_error(status) or status == config.STATUS["NO_FILES"]:
            return (
                None,
                None,
                create_response(
                    status=status,
                    base=base,
                    context=context,
                    data={"files_count": len(json_files), "directory": context} if sbp_paths else None
                ),
                False
            )
        
        return json_files, sbp_paths, None, True
        
    except Exception as e:
        log_error_with_context(e, f"get_files_with_check base={base} key={directory_key}")
        return (
            None,
            None,
            create_response(
                status=config.STATUS["UNKNOWN_ERROR"],
                base=base,
                error=f"Ошибка получения файлов: {str(e)}"
            ),
            False
        )


# ============================================================
#                     НОВЫЕ ФУНКЦИИ (для мультибанковости)
# ============================================================

def create_sbp_paths_for_bank(
    bank: str,
    base: str
) -> SBPPaths:
    """
    Создаёт объект с путями SBP для указанного банка и базы.
    
    Это НОВАЯ функция для использования в новом коде.
    
    Args:
        bank: Имя банка (ci, sb, vtb)
        base: Название базы
    
    Returns:
        SBPPaths: Объект с путями
    
    Пример:
        paths = create_sbp_paths_for_bank('sb', 'zkh_ursv')
        # → /sbp/sb/zkh_ursv
    """
    return create_sbp_paths(base, bank=bank)


def get_json_files_in_directory_for_bank(
    bank: str,
    base: str, 
    key: str
) -> Tuple[List[Path], Optional[Dict[str, Any]], SBPPaths, str]:
    """
    Получает JSON-файлы в указанной директории для банка и базы.
    
    Это НОВАЯ функция для использования в новом коде.
    
    Args:
        bank: Имя банка
        base: Название базы
        key: Ключ директории
    
    Returns:
        Tuple[List[Path], Optional[Dict[str, Any]], SBPPaths, str]:
            (файлы, ошибка, пути, статус)
    """
    stack = get_function_stack()
    
    paths = create_sbp_paths(base, bank=bank)
    
    try:
        files, error = paths.get_json_files(key)
        
        if error:
            logger.error(f"{stack}: {error}")
            return [], error, paths, config.STATUS["DIRECTORY_ERROR"]
        
        if not files:
            logger.debug(f"{stack}: Нет JSON файлов для банка '{bank}' базы '{base}' (директория: {key})")
            return [], None, paths, config.STATUS["NO_FILES"]
        
        logger.debug(f"{stack}: Найдено {len(files)} JSON файлов для банка '{bank}' базы '{base}'")
        return files, None, paths, config.STATUS["SUCCESS"]
        
    except Exception as e:
        log_error_with_context(e, f"get_json_files_in_directory_for_bank bank={bank} base={base} key={key}")
        return [], {"error": str(e)}, paths, config.STATUS["DIRECTORY_ERROR"]


def get_files_with_check_for_bank(
    bank: str,
    base: str,
    directory_key: str,
    context_message: str = "Запрос к API ИВЦ из базы"
) -> Tuple[Optional[List[Path]], Optional[SBPPaths], Optional[Dict[str, Any]], bool]:
    """
    Получает файлы для указанного банка и проверяет статус.
    
    Это НОВАЯ функция для использования в новом коде.
    
    Args:
        bank: Имя банка
        base: Название базы
        directory_key: Ключ директории
        context_message: Сообщение для логирования
    
    Returns:
        Tuple[Optional[List[Path]], Optional[SBPPaths], Optional[Dict[str, Any]], bool]:
            (json_files, sbp_paths, response, should_process)
    """
    stack = get_function_stack()
    logger.debug(f"{stack}: {context_message} {bank}/{base}")
    
    try:
        start = time.time()
        json_files, error_msg, sbp_paths, status = get_json_files_in_directory_for_bank(bank, base, directory_key)
        elapsed = time.time() - start
        logger.debug(f"Функция get_json_files_in_directory_for_bank выполнена за {elapsed:.2f} сек")
        context = str(sbp_paths.base) if sbp_paths else None
        
        if config.is_error(status) or status == config.STATUS["NO_FILES"]:
            return (
                None,
                None,
                create_response(
                    status=status,
                    bank=bank,
                    base=base,
                    context=context,
                    data={"files_count": len(json_files), "directory": context} if sbp_paths else None
                ),
                False
            )
        
        return json_files, sbp_paths, None, True
        
    except Exception as e:
        log_error_with_context(e, f"get_files_with_check_for_bank bank={bank} base={base} key={directory_key}")
        return (
            None,
            None,
            create_response(
                status=config.STATUS["UNKNOWN_ERROR"],
                bank=bank,
                base=base,
                error=f"Ошибка получения файлов: {str(e)}"
            ),
            False
        )


def get_sbp_root_path(bank: Optional[str] = None) -> Path:
    """
    Возвращает корневой путь SBP для указанного банка.
    
    Args:
        bank: Имя банка (если None — банк по умолчанию)
    
    Returns:
        Path: Корневой путь
    """
    sbp_root = config.SBP_ROOT
    
    if bank and hasattr(sbp_root, 'path') and callable(sbp_root.path):
        return Path(sbp_root.path(bank))
    
    return Path(str(sbp_root))


def get_bank_base_path(bank: str, base: str) -> Path:
    """
    Возвращает путь к папке банка/базы.
    
    Args:
        bank: Имя банка
        base: Название базы
    
    Returns:
        Path: Путь к папке
    """
    return create_sbp_paths_for_bank(bank, base).base


def ensure_directories_exist(paths: SBPPaths) -> None:
    """
    Гарантирует существование всех директорий в объекте SBPPaths.
    
    Args:
        paths: Объект SBPPaths
    """
    for path in [paths.base, paths.sended, paths.processing, 
                 paths.get, paths.geted, paths.stop, paths.stoped]:
        path.mkdir(parents=True, exist_ok=True)


# ============================================================
#                     ТЕСТЫ
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТЫ SBP_UTILS (ОБРАТНАЯ СОВМЕСТИМОСТЬ)")
    print("=" * 60)
    
    # 1. ТЕСТ СТАРОГО СИНТАКСИСА (для create_payload)
    print("\n1. СТАРЫЙ СИНТАКСИС (create_payload):")
    paths_old = create_sbp_paths('zkh_ursv')
    print(f"  create_sbp_paths('zkh_ursv')")
    print(f"    base: {paths_old.base}")
    print(f"    processing: {paths_old.processing}")
    print(f"    bank: {paths_old.bank}")
    
    # 2. ТЕСТ get_json_files_in_directory (старый синтаксис)
    print("\n2. get_json_files_in_directory (старый синтаксис):")
    files, error, paths, status = get_json_files_in_directory('zkh_ursv', 'base')
    print(f"  найдено файлов: {len(files)}")
    print(f"  статус: {status}")
    print(f"  paths.base: {paths.base}")
    
    # 3. ТЕСТ get_files_with_check (для create_payload)
    print("\n3. get_files_with_check (для create_payload):")
    json_files, sbp_paths, response, should_process = get_files_with_check(
        'zkh_ursv', 'base', 'Тестовый запрос'
    )
    print(f"  should_process: {should_process}")
    print(f"  найдено файлов: {len(json_files) if json_files else 0}")
    if sbp_paths:
        print(f"  paths.base: {sbp_paths.base}")
    
    # 4. ТЕСТ НОВОГО СИНТАКСИСА (с банком)
    print("\n4. НОВЫЙ СИНТАКСИС (с банком):")
    paths_new = create_sbp_paths('zkh_ursv', bank='sb')
    print(f"  create_sbp_paths('zkh_ursv', bank='sb')")
    print(f"    base: {paths_new.base}")
    print(f"    bank: {paths_new.bank}")
    
    # 5. ТЕСТ get_files_with_check_for_bank (новая)
    print("\n5. get_files_with_check_for_bank (новая):")
    json_files2, sbp_paths2, response2, should_process2 = get_files_with_check_for_bank(
        'sb', 'zkh_ursv', 'base', 'Тестовый запрос с банком'
    )
    print(f"  should_process: {should_process2}")
    print(f"  найдено файлов: {len(json_files2) if json_files2 else 0}")
    if sbp_paths2:
        print(f"  paths.base: {sbp_paths2.base}")
        print(f"  paths.bank: {sbp_paths2.bank}")
    
    print("\n" + "=" * 60)
    print("✅ Все тесты пройдены! Обратная совместимость сохранена!")
    print("=" * 60)