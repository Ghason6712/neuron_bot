import numpy as np
import onnxruntime as ort
import os
import tempfile

# ... ВСТАВЬТЕ ВЕСЬ ВАШ СКРИПТ СЮДА ...
# но замените жесткие имена файлов на параметры:

def process_files(roh_path, rov_path, z_path, output_path=None):
    """Основная функция обработки файлов."""
    try:
        # Загружаем данные
        domain_h = load_obl_file_with_separator(roh_path)  
        domain_v = load_obl_file_with_separator(rov_path)  
        z = np.loadtxt(z_path, dtype=np.float32, skiprows=1)
        
        # Инициализируем решатель
        solver = BKZStd6GradientNNSolver()
        
        # Получаем предсказания
        all_predictions = solver(domain_h, domain_v, z)
        
        config_names = [filename for _, filename in SOLVER_CONFIGS]
        
        # Создаём временный файл, если путь не указан
        if output_path is None:
            import tempfile
            fd, output_path = tempfile.mkstemp(suffix='.dat', prefix='predictions_')
            os.close(fd)
        
        # Сохраняем результаты
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
        
        return output_path
        
    except Exception as e:
        raise Exception(f"Ошибка обработки файлов: {str(e)}")

# ... остальной ваш код ...