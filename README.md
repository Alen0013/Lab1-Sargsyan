# ЛР1 · Вариант 25 · Калибровка

**Саргсян Ален Артурович**

Репозиторий: [Alen0013/calibration-Lab_First](https://github.com/Alen0013/calibration-Lab_First).

Цель работы — настроить проверяемый порядок изменений в Git и выполнить разведочный анализ данных своего варианта. Программа `lab1.py` проверяет исходные данные, считает сводки pandas, строит графики и показывает проблему калибровки вероятностей. Результаты сохраняются в `reports/LAB1/`, эксперименты — в локальном MLflow.

## Какие файлы за что отвечают

| Файл | Назначение |
| --- | --- |
| [lab1.py](lab1.py) | Загрузка и проверка данных, EDA, диаграмма калибровки, повтор анализа |
| [check_staged.py](check_staged.py) | Проверка файлов в индексе Git: секреты и превышение размера |
| [negative_controls.py](negative_controls.py) | Три реальные попытки ошибочного коммита с сохранением журнала |
| [configs/lab1.yaml](configs/lab1.yaml) | Автор, вариант, seed и параметры анализа; проверяются Pydantic |
| [tests/test_lab1.py](tests/test_lab1.py) | Автоматические проверки расчётов и валидации |
| [.pre-commit-config.yaml](.pre-commit-config.yaml) | Стиль, форматирование и проверки перед коммитом |
| [.github/workflows/ci.yml](.github/workflows/ci.yml) | Проверка проекта на GitHub |
| [reports/LAB1](reports/LAB1/) | Отчёт, таблицы, графики и фактические журналы выполнения |

## Запуск на Windows

Нужны Python 3.12 и Git. Откройте PowerShell в корне проекта. Если `.venv312` уже создано, пропустите первую команду:

```powershell
py -3.12 -m venv .venv312
.\.venv312\Scripts\python.exe -m pip install -r requirements.txt
$env:Path = "$PWD\.venv312\Scripts;$env:Path"
python lab1.py verify
python lab1.py run
```

Строка с `Path` выбирает Python созданного окружения для этого терминала. В PyCharm укажите интерпретатор `.venv312\Scripts\python.exe`. Программа работает в терминале; результат анализа открывается в файлах отчёта и графиков.

На Linux/macOS создайте окружение через `python3.12 -m venv .venv312`, активируйте `source .venv312/bin/activate` и выполните `python -m pip install -r requirements.txt`. Остальные команды одинаковы.

## Команды и результаты

| Команда | Результат |
| --- | --- |
| `python lab1.py prepare` | Получает отсутствующие данные и сверяет закреплённый хеш |
| `python lab1.py verify` | Проверяет размер и SHA-256 исходного файла |
| `python lab1.py run` | Создаёт сводки, графики, метрики и новый MLflow-прогон |
| `python lab1.py tamper` | Проверяет обнаружение подмены временной копии данных |
| `python lab1.py reproduce` | Выполняет два анализа и сравнивает детерминированные результаты |
| `python negative_controls.py` | Проверяет блокировку стиля, искусственного секрета и большого файла |
| `python -m pytest -q` | Запускает автоматические тесты |

Исходный CSV входит в проект. При несовпадении хеша программа сообщает ошибку; эталон не пересчитывается под изменённый файл. Негативные контроли работают с временными копиями и отдельным временным Git-репозиторием.

## Git и проверки перед коммитом

Команды Git выполняются в настоящем клоне. Папка из ZIP позволяет запустить анализ, но не содержит историю `.git`. Получить клон опубликованной версии:

```powershell
git clone https://github.com/Alen0013/calibration-Lab_First.git calibration-lab_1
```

Внутри клона подготовьте окружение по инструкции выше и установите hook:

```powershell
python -m pre_commit install
python -m pre_commit run --all-files --show-diff-on-failure
```

Обычный порядок изменения: `git switch -c fix/lab1-change`, редактирование, проверки, `git add <изменённые файлы>`, `git commit -m "docs: clarify lab1 results"`, `git push -u origin fix/lab1-change`. Затем создайте pull request в `main`, заполните [шаблон](.github/pull_request_template.md) и дождитесь успешного `quality` именно для нового коммита. Главная ветка защищается в настройках GitHub. Внешний просмотр другим человеком отмечается после его выполнения.

Наличие конфигурации pre-commit не устанавливает hook автоматически. `.gitignore` исключает окружения, `mlruns/` и видео; `.gitattributes` задаёт окончания строк. Старые ветки остаются частью истории разработки.

## Что исследуется

Набор [Breast Cancer Wisconsin Diagnostic](https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic), лицензия CC BY 4.0; числовая версия из [scikit-learn 1.8.0](https://raw.githubusercontent.com/scikit-learn/scikit-learn/1.8.0/sklearn/datasets/data/breast_cancer.csv). Паспорт, размер и SHA-256 приведены в отчёте и [манифесте](hash_manifest.json).

EDA описывает поля, пропуски, аномальные значения, распределения, доли классов и корреляции. Для варианта 25 построена диаграмма: средняя предсказанная вероятность сопоставляется с долей положительных исходов. Масштабирование и логистическая регрессия обучаются на train, сигмоидальный калибратор — на calibration, оценка выполняется на test. Калибровка не обязана улучшить метрики на конкретной выборке; вывод формулируется по полученным значениям.

