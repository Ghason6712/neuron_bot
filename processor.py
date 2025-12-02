import numpy as np
import onnxruntime as ort
import os
import tempfile
import sys


def format_depth_value(depth):
    """Форматирование значения глубины."""
    if depth.is_integer():
        return f"{depth:.0f}"
    else:
        return f"{depth:.1f}"


SOLVER_CONFIGS = [
    (0, "A0.4M0.1N"),
    (1, "A1.0M0.1N"),
    (2, "A2.0M0.5N"),
    (3, "A-2.0M0.5N"),
    (4, "A4.0M0.5N"),
    (5, "A8.0M1.0N")
]

# Константы
BUFFER_DEPTH = 20.0
MODEL_STEP = 0.1
DISTANCE_THRESHOLD = 1.0
LOG_REPLACE_VALUE = -1.0

# Глобальные переменные для обработки
_first_elements = []
_session_cache = None


def load_obl_file_with_separator(filepath):
    """Загрузка входных файлов."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]
    
    line_lengths = [len(line.split()) for line in lines]
    total_values = sum(line_lengths) + max(0, len(lines) - 1)
    
    data = np.empty(total_values, dtype=np.float32)
    
    pos = 0
    separator = -1.0
    for i, line in enumerate(lines):
        values = np.fromstring(line, sep=' ', dtype=np.float32)
        data[pos:pos + len(values)] = values
        pos += len(values)
        if i != len(lines) - 1:
            data[pos] = separator
            pos += 1

    return data


def _find_layer_boundaries(domain_data):
    """Нахождение границ слоев."""
    separator_indices = np.where(domain_data == -1.0)[0]
    
    split_indices = np.concatenate(([-1], separator_indices, [len(domain_data)]))
    
    segments = []
    for i in range(len(split_indices) - 1):
        start = split_indices[i] + 1
        end = split_indices[i + 1]
        if end > start:
            segment = domain_data[start:end]
            segments.append(segment.astype(np.float32))
    
    return segments


def crop_input_model_bkz_std_6_gradient(domain_h, domain_v, z):
    """Обработка слоев."""
    global _first_elements
    
    domain_h_list = _find_layer_boundaries(domain_h)
    domain_v_list = _find_layer_boundaries(domain_v)
    
    domain_depth_columns = np.vstack([layer[:2] for layer in domain_h_list])
    start_depth = z[0] - BUFFER_DEPTH
    end_depth = z[-1] + BUFFER_DEPTH
    
    # Обработка начальной границы
    if start_depth < domain_depth_columns[0, 0]:
        domain_h_list[0][0] = domain_v_list[0][0] = start_depth
    elif start_depth > domain_depth_columns[0, 0]:
        mask = start_depth < domain_depth_columns[:, 1]
        if np.any(mask):
            first_match_idx = np.argmax(mask)
            domain_h_list = domain_h_list[first_match_idx:]
            domain_v_list = domain_v_list[first_match_idx:]
            domain_h_list[0][0] = domain_v_list[0][0] = start_depth
    
    # Обработка конечной границы
    if end_depth > domain_depth_columns[-1, 1]:
        domain_h_list[-1][1] = domain_v_list[-1][1] = end_depth
    elif end_depth < domain_depth_columns[-1, 1]:
        reversed_mask = end_depth > domain_depth_columns[::-1, 0]
        if np.any(reversed_mask):
            last_match_idx = (
                len(domain_depth_columns) - np.argmax(reversed_mask) - 1
            )
            if last_match_idx < len(domain_h_list) - 1:
                domain_h_list = domain_h_list[:last_match_idx + 1]
                domain_v_list = domain_v_list[:last_match_idx + 1]
            domain_h_list[-1][1] = domain_v_list[-1][1] = end_depth
    
    _first_elements = [arr[0] for arr in domain_h_list] + [end_depth]
    
    return domain_h_list, domain_v_list


def create_model_for_nn_bkz_std_6_gradient(domain_h_list, domain_v_list):
    """Создание модели сопротивлений."""
    top_depth = np.round(domain_h_list[0][0], 3)
    bottom_depth = np.round(domain_h_list[-1][1], 3)
    
    n_depths = int((bottom_depth - top_depth) / MODEL_STEP) + 1
    nn_resistivity_model = np.zeros((n_depths, 6), dtype=np.float32)

    all_data_rows = []
    all_start_indices = []
    all_end_indices = []
    
    for layer_h, layer_v in zip(domain_h_list, domain_v_list):
        if layer_h.shape[0] == 7:  # изотропный слой
            data_row = np.hstack((layer_h[2:], layer_h[-1]))
        else:  # анизотропный слой
            data_row = np.hstack((
                layer_h[2:5], 0.0, layer_h[-1], layer_v[-1]
            ))
        
        start_idx = int(np.round((layer_h[0] - top_depth) / MODEL_STEP))
        end_idx = int(np.round((layer_h[1] - top_depth) / MODEL_STEP))
        
        start_idx = max(0, min(start_idx, n_depths - 1))
        end_idx = max(0, min(end_idx, n_depths - 1))
        
        if start_idx <= end_idx:
            all_data_rows.append(data_row)
            all_start_indices.append(start_idx)
            all_end_indices.append(end_idx)
    
    for data_row, start_idx, end_idx in zip(
        all_data_rows, all_start_indices, all_end_indices
    ):
        nn_resistivity_model[start_idx:end_idx + 1] = data_row
    
    return nn_resistivity_model


def modify_matrix(matrix, first_elements):
    """Модификация входной матрицы."""
    matrix = np.asarray(matrix, dtype=np.float64)
    sorted_elements = sorted(first_elements)
    
    num_rows = matrix.shape[0]
    n_elements = len(sorted_elements)
    
    dist_to_next_col = np.empty(num_rows, dtype=np.float64)
    dist_to_prev_col = np.empty(num_rows, dtype=np.float64)
    
    current_position = sorted_elements[0]
    border_index = 0
    model_step = MODEL_STEP
    threshold = DISTANCE_THRESHOLD
    replace_val = LOG_REPLACE_VALUE
    zero_tol = 1e-4
    
    borders = sorted_elements
    last_valid_index = n_elements - 2
    
    for i in range(num_rows):
        current_layer_start = borders[border_index]
        
        next_border_index = border_index + 1
        has_next = next_border_index < n_elements
        
        if has_next:
            next_border = borders[next_border_index]
            
            position_diff = current_position - next_border
            if (abs(position_diff) < zero_tol and 
                border_index < last_valid_index):
                border_index += 1
                current_layer_start = borders[border_index]
                next_border_index = border_index + 1
                has_next = next_border_index < n_elements
                next_border = borders[next_border_index] if has_next else None
        else:
            next_border = None
        
        if has_next:
            dist_to_next = next_border - current_position
            if dist_to_next > threshold:
                dist_to_next = replace_val
        else:
            dist_to_next = replace_val
        
        dist_to_prev = current_position - current_layer_start
        if dist_to_prev > threshold:
            dist_to_prev = replace_val
        
        if abs(dist_to_prev) < zero_tol:
            dist_to_prev = 0.0
        if has_next and abs(dist_to_next) < zero_tol:
            dist_to_next = 0.0
        
        dist_to_next_col[i] = dist_to_next
        dist_to_prev_col[i] = dist_to_prev
        
        current_position += model_step

        if (has_next and current_position > next_border and 
            border_index <= last_valid_index):
            border_index += 1
    
    result_matrix = np.column_stack((
        dist_to_next_col.reshape(-1, 1), 
        dist_to_prev_col.reshape(-1, 1), 
        matrix
    ))
    
    result_matrix[:, [-1, -2]] = result_matrix[:, [-2, -1]]
    
    return result_matrix


def normalize_nn_input_bkz_std_6_gradient(nn_input):
    """Нормализация входных данных."""
    nn_input_normalized = nn_input.copy()
    
    log_columns = np.array([2, 4, 7, 6])
    nn_input_normalized[:, log_columns] = np.log(
        nn_input_normalized[:, log_columns]
    )
    
    zero_mask = nn_input_normalized[:, 5] == 0
    nn_input_normalized[zero_mask, 5] = LOG_REPLACE_VALUE
    
    return nn_input_normalized


class BKZStd6GradientNNSolver:
    """Класс решателя нейронной сети."""
    
    def __init__(self, model_path="BKZ_solver_900k.onnx"):
        self._session = None
        self._input_name = None
        self._output_name = None
        self.model_path = model_path

    def __call__(self, domain_h, domain_v, z):
        return self._process_inputs(domain_h, domain_v, z)

    def _process_inputs(self, domain_h, domain_v, z):
        if self._session is None:
            self._init_onnx_session()

        domain_h_processed, domain_v_processed = crop_input_model_bkz_std_6_gradient(
            domain_h, domain_v, z
        )
        nn_input = create_model_for_nn_bkz_std_6_gradient(
            domain_h_processed, domain_v_processed
        )
        nn_input = modify_matrix(nn_input, _first_elements)
        nn_input_normalized = normalize_nn_input_bkz_std_6_gradient(nn_input)
        nn_input_normalized = np.expand_dims(nn_input_normalized, 0).astype(
            np.float32
        )
        
        raw_predictions = self._session.run(
            [self._output_name], 
            {self._input_name: nn_input_normalized}
        )[0]
        
        processed_predictions = self._process_predictions(raw_predictions, z)
        
        return processed_predictions

    def _init_onnx_session(self):
        global _session_cache
        
        if _session_cache is None:
            # Проверяем наличие файла модели
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(
                    f"Модель ONNX не найдена: {self.model_path}. "
                    "Убедитесь, что файл находится в корневой директории."
                )
            
            try:
                _session_cache = ort.InferenceSession(
                    self.model_path,
                    providers=['CPUExecutionProvider']
                )
                print(f"✅ Модель загружена: {self.model_path}")
            except Exception as e:
                raise Exception(f"Ошибка загрузки модели ONNX: {str(e)}")
        
        self._session = _session_cache
        self._input_name = self._session.get_inputs()[0].name
        self._output_name = self._session.get_outputs()[0].name

    def _process_predictions(self, predictions, z):
        step = np.round(z[1] - z[0], 1)
        crop_size = int(np.round((z[-1] - z[0]) / 0.1)) + 1
    
        total_points = predictions.shape[1]
        if total_points > crop_size:
            start_crop = (total_points - crop_size) // 2
            predictions_cropped = predictions[
                0, start_crop:start_crop + crop_size
            ]
        else:
            predictions_cropped = predictions[0, :crop_size]
        
        predictions_exp = np.exp(predictions_cropped)
    
        if step == 0.2:
            return predictions_exp[::2]
    
        return predictions_exp


def process_files(roh_path, rov_path, z_path, output_path=None):
    """
    Основная функция обработки файлов.
    
    Args:
        roh_path: путь к файлу roH.obl
        rov_path: путь к файлу roV.obl
        z_path: путь к файлу z.ini
        output_path: путь для сохранения результата (опционально)
    
    Returns:
        str: путь к созданному файлу с результатами
    """
    try:
        print(f"🔍 Начинаю обработку файлов:")
        print(f"   roH: {roh_path}")
        print(f"   roV: {rov_path}")
        print(f"   z: {z_path}")
        
        # Проверяем существование файлов
        for path in [roh_path, rov_path, z_path]:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Файл не найден: {path}")
        
        # Загружаем данные
        print("📥 Загружаю данные из файлов...")
        domain_h = load_obl_file_with_separator(roh_path)  
        domain_v = load_obl_file_with_separator(rov_path)  
        
        # Для z.ini пропускаем первую строку (заголовок)
        z = np.loadtxt(z_path, dtype=np.float32, skiprows=1)
        
        if len(z) == 0:
            raise ValueError("Файл z.ini пуст или имеет неверный формат")
        
        print(f"✅ Данные загружены. Глубин: {len(z)}")
        
        # Инициализируем решатель
        print("🧠 Инициализирую решатель...")
        solver = BKZStd6GradientNNSolver()
        
        # Получаем предсказания
        print("⚙ Выполняю вычисления...")
        all_predictions = solver(domain_h, domain_v, z)
        
        config_names = [filename for _, filename in SOLVER_CONFIGS]
        
        # Создаём временный файл, если путь не указан
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.dat', prefix='predictions_')
            os.close(fd)
            print(f"📄 Создан временный файл: {output_path}")
        else:
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Сохраняем результаты
        print("💾 Сохраняю результаты...")
        with open(output_path, 'w', encoding='utf-8') as f:
            header = "DEPT  " + "  ".join(config_names)
            f.write(header + "\n")
            
            for i in range(len(z)):
                depth_str = format_depth_value(z[i])
                pred_str = "  ".join([
                    f"{pred:10.3f}" for pred in all_predictions[i]
                ])
                line = f"{depth_str:>6}  {pred_str}"
                f.write(line + "\n")
        
        print(f"✅ Результаты сохранены в: {output_path}")
        print(f"📊 Обработано строк: {len(z)}")
        
        return output_path
        
    except FileNotFoundError as e:
        raise Exception(f"Файл не найден: {str(e)}")
    except ValueError as e:
        raise Exception(f"Ошибка формата файла: {str(e)}")
    except Exception as e:
        raise Exception(f"Ошибка обработки файлов: {str(e)}")


def get_file_type_by_content(filepath):
    """
    Определяет тип файла по его содержимому.
    
    Returns:
        'roh', 'rov', 'z' или 'unknown'
    """
    try:
        filename = os.path.basename(filepath).lower()
        
        # Сначала по имени
        if 'roh' in filename:
            return 'roh'
        elif 'rov' in filename:
            return 'rov'
        elif 'z' in filename or filename.endswith('.ini'):
            return 'z'
        
        # Если не определили по имени, пробуем по содержимому
        if filename.endswith('.obl'):
            with open(filepath, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    return 'unknown'
                
                values = first_line.split()
                # roH обычно имеет 5 или 7 значений в строке
                # roV обычно имеет 6 или 8 значений в строке
                if len(values) == 5 or len(values) == 7:
                    return 'roh'
                elif len(values) == 6 or len(values) == 8:
                    return 'rov'
        
        elif filename.endswith('.ini'):
            return 'z'
            
    except Exception:
        pass
    
    return 'unknown'


# Тестовая функция для локальной проверки
if __name__ == "__main__":
    print("🧪 Тестирование processor.py")
    
    # Создаем тестовые файлы для проверки
    test_dir = tempfile.mkdtemp(prefix="test_processor_")
    
    # Тестовый roH.obl
    roh_test = os.path.join(test_dir, "roH.obl")
    with open(roh_test, 'w') as f:
        f.write("100.0 200.0 1.0 2.0 3.0 4.0 5.0\n")
        f.write("200.0 300.0 2.0 3.0 4.0 5.0 6.0\n")
    
    # Тестовый roV.obl  
    rov_test = os.path.join(test_dir, "roV.obl")
    with open(rov_test, 'w') as f:
        f.write("100.0 200.0 1.0 2.0 3.0 4.0 5.0 6.0\n")
        f.write("200.0 300.0 2.0 3.0 4.0 5.0 6.0 7.0\n")
    
    # Тестовый z.ini
    z_test = os.path.join(test_dir, "z.ini")
    with open(z_test, 'w') as f:
        f.write("Глубина\n")
        for i in range(10):
            f.write(f"{100 + i * 10}\n")
    
    try:
        result = process_files(roh_test, rov_test, z_test)
        print(f"✅ Тест пройден успешно!")
        print(f"📄 Результат в: {result}")
        
        # Показываем первые несколько строк результата
        with open(result, 'r') as f:
            lines = f.readlines()
            print("\nПервые 3 строки результата:")
            for i in range(min(3, len(lines))):
                print(f"  {lines[i].strip()}")
                
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
    
    finally:
        # Очистка тестовых файлов
        import shutil
        try:
            shutil.rmtree(test_dir)
        except:
            pass