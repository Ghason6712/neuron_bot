import os
import tempfile
import shutil

class FileManager:
    """Менеджер для работы с временными файлами."""
    
    def __init__(self):
        self.user_files = {}  # user_id: [file_paths]
    
    def add_file(self, user_id, file_path):
        if user_id not in self.user_files:
            self.user_files[user_id] = []
        self.user_files[user_id].append(file_path)
    
    def get_user_files(self, user_id):
        return self.user_files.get(user_id, [])
    
    def clear_user_files(self, user_id):
        """Удаляет все файлы пользователя."""
        if user_id in self.user_files:
            for file_path in self.user_files[user_id]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    # Удаляем папку, если она пустая
                    folder = os.path.dirname(file_path)
                    if os.path.exists(folder) and not os.listdir(folder):
                        shutil.rmtree(folder)
                except:
                    pass
            del self.user_files[user_id]

file_manager = FileManager()


def get_file_type(filename):
    """Определяет тип файла по имени."""
    name_lower = filename.lower()
    
    if 'roh' in name_lower:
        return 'roh'
    elif 'rov' in name_lower:
        return 'rov'
    elif 'z' in name_lower or filename.endswith('.ini'):
        return 'z'
    else:
        # Попробуем определить по расширению
        if filename.endswith('.obl'):
            # Нужно посмотреть содержимое
            try:
                with open(filename, 'r') as f:
                    first_line = f.readline().strip()
                    values = first_line.split()
                    if len(values) > 5:
                        return 'rov'
                    else:
                        return 'roh'
            except:
                return 'unknown'
        return 'unknown'