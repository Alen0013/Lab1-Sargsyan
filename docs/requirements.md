# ЛР1: требования и свидетельства

**Саргсян Ален Артурович · вариант 25 · калибровка.**

Основание — общие требования методички, раздел «ЛР 1» и карточка варианта 25. Проект выполняет разведочный анализ и проверку изменений в Git.

| Пункт | Где проверять | Критерий |
| --- | --- | --- |
| Репозиторий и ветки | `git log --graph --oneline --all`, GitHub | Реальная история; изменения оформлены отдельными коммитами и PR |
| Защита `main` | GitHub Settings | Правило действует на сервере; новый PR проходит `quality` |
| Шаблон изменения | [PR template](../.github/pull_request_template.md) | Задача, изменения, команды и результат проверок заполнены |
| Исключения и окончания строк | [.gitignore](../.gitignore), [.gitattributes](../.gitattributes) | Окружения и локальные результаты исключены, правила строк заданы |
| Pre-commit | [.pre-commit-config.yaml](../.pre-commit-config.yaml) | Стиль, секреты, размер и быстрые проверки; hook установлен в клоне |
| Копия конфигурации | [precommit_config.yaml](../reports/LAB1/precommit_config.yaml) | Совпадает с действующим файлом |
| Три блокировки | [precommit_block.log](../reports/LAB1/precommit_block.log), [precommit_controls.json](../reports/LAB1/precommit_controls.json) | Стиль, искусственный секрет и большой бинарный файл отклонены; HEAD сохранён |
| Источник, лицензия, поля и разбиение | [lab1_report.md](../reports/LAB1/lab1_report.md) | Паспорт данных заполнен |
| Размеры и хеши данных | [hash_manifest.json](../hash_manifest.json), [копия](../reports/LAB1/hash_manifest.json) | `python lab1.py verify` подтверждает совпадение |
| EDA средствами pandas | [eda_stats.csv](../reports/LAB1/eda_stats.csv), [feature_stats.csv](../reports/LAB1/feature_stats.csv) | Объём, типы, пропуски, аномалии и сводки получены из данных |
| Распределения, классы, связи | [figures](../reports/LAB1/figures/), [correlations.csv](../reports/LAB1/correlations.csv) | Графики matplotlib/seaborn имеют числовые подписи |
| Проблема варианта 25 | [calibration.png](../reports/LAB1/figures/calibration.png), [calibration_bins.csv](../reports/LAB1/calibration_bins.csv) | Вероятности сопоставлены с долей исходов; качество измерено |
| Нумерованные выводы | [Отчёт](../reports/LAB1/lab1_report.md) | Один основной числовой результат в каждом выводе; ссылка на расчёт |
| Подмена данных | [hash_tamper.log](../reports/LAB1/hash_tamper.log), [hash_tamper.json](../reports/LAB1/hash_tamper.json) | Изменённая временная копия отклонена; оригинал сохранён |
| Повтор EDA | [reproducibility.json](../reports/LAB1/reproducibility.json), [журнал](../reports/LAB1/reproducibility.log) | Два настоящих запуска совпадают по указанным результатам |
| Pydantic и конфигурация | [lab1.py](../lab1.py), [lab1.yaml](../configs/lab1.yaml) | Невалидные настройки отклоняются |
| MLflow и происхождение чисел | [results.json](../reports/LAB1/results.json), [run_environment.json](../reports/LAB1/run_environment.json) | Есть `run_id`, commit, хеш данных и версии; `mlruns/` вне Git |
| Автоматические тесты | [test_lab1.py](../tests/test_lab1.py), [tests.log](../reports/LAB1/tests.log) | Реальный успешный запуск pytest |
| CI, checklist, просмотр | [Actions](https://github.com/Alen0013/calibration-Lab_First/actions), заполненный PR | CI относится к передаваемому коммиту; внешний просмотр отмечается после выполнения |
| Скринкаст | [Сценарий](video_script.md), отдельное видео | 3–5 минут; действия, результат, измеренное качество и связь с отчётом |
| Сдача | Архив, ссылка, отчёт и видео | Все материалы приложены в систему курса |

Локальный журнал подтверждает локальное исполнение. Серверный статус относится к конкретному SHA: успешный старый CI не заменяет проверку нового изменения. Авторская проверка и внешнее ревью другим человеком отмечаются отдельно.

В шапке отчёта обязательны вариант, работа, дата, автор, хеш коммита и хеши данных. Старому опыту не присваивается новый commit вручную: после изменения кода выполняется новый запуск.

Нейросеть, синтетика, режим чанков и нагрузочные испытания относятся к следующим работам. В ЛР1 LogReg и сигмоидальная калибровка служат иллюстрацией проблемы вероятностей. Ухудшение метрики допустимо, если оно измерено и объяснено.
