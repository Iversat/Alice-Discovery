![Alice Discovery — обнаружение сервисов в локальной сети](docs/banner.svg)

# Alice Discovery

Я разрабатываю Alice Discovery для поиска объявлений умных колонок в локальной сети. Инструмент получает mDNS/DNS-SD-записи и показывает адреса, порты и TXT-свойства сервисов.

**Python 3.11+** · **mDNS / DNS-SD** · **IPv4 + IPv6** · **JSON**

[Установка](#установка) · [Использование](#использование) · [Python API](#python-api) · [Проверки](docs/TESTING.md)

Я веду проект независимо от производителей устройств. Обнаружение сервисов не предоставляет управление колонками; мультирум и синхронное воспроизведение в Alice Discovery не реализованы.

## Установка

```powershell
git clone https://github.com/Iversat/Alice-Discovery.git
cd Alice-Discovery
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe multiroom_scanner.py
```

В Linux и macOS используйте `python3 -m venv .venv` и `.venv/bin/python`. После установки доступна команда `alice-discovery`. Команду `ls-discovery` и файл `multiroom_scanner.py` я сохранил для совместимости.

## Обновление прежней установки

Если вы устанавливали проект под старым именем, я рекомендую удалить прежний пакет из того же виртуального окружения перед обновлением: разные пакеты могут содержать одинаковые Python-модули и команды.

```powershell
.\.venv\Scripts\python.exe -m pip uninstall ls-discovery alice-discovery-research
.\.venv\Scripts\python.exe -m pip install -e "."
```

## Использование

```bash
# По умолчанию сканирование длится 10 секунд.
python multiroom_scanner.py

# Выбрать длительность и получить JSON.
python multiroom_scanner.py --duration 5 --json > scan-results.json

# Искать определённый тип сервиса.
python multiroom_scanner.py --service _yandexio._tcp.local.

# Выбрать интерфейс по его локальному IP.
python multiroom_scanner.py --interface 192.0.2.20 --duration 5
```

`--service` и `--interface` можно повторять. Адрес `192.0.2.20` приведён как пример; замените его адресом сетевого интерфейса. Для диагностики используйте `--verbose`, для справки — `--help`.

По умолчанию я включил следующие типы сервисов:

| Тип | Назначение |
| --- | --- |
| `_yandexio._tcp.local.` | Объявления устройств Яндекса |
| `_yandexstation._tcp.local.` | Объявления Станций |
| `_googlecast._tcp.local.` | Google Cast |
| `_spotify-connect._tcp.local.` | Spotify Connect |

У одного устройства может быть несколько объявлений. Я сохраняю каждое отдельно и учитываю обновления и удаления. Число записей обозначает количество сервисов, а не физических устройств.

Пример с вымышленным устройством:

```text
Найдено сервисов: 1

01  speaker-demo
    Сервис   _yandexio._tcp.local.
    Адреса   192.0.2.10, 2001:db8::1
    Порт     1961
    Имя      Demo._yandexio._tcp.local.
    TXT      {"platform": "demo"}
```

## Python API

```python
from multiroom_scanner import scan_local_network_for_speakers

records = scan_local_network_for_speakers(scan_duration_seconds=3)
for record in records:
    print(record["service_name"], record["addresses"])
```

Функция возвращает список словарей с ключами `name`, `server`, `service_name`, `type`, `addresses`, `port`, `properties`. Она не печатает результат. Снимок данных защищён от изменения рабочего потока; ресурсы закрываются при завершении, ошибке и Ctrl+C.

## Если ничего не найдено

Компьютер и колонка должны находиться в сети, где доступен обмен mDNS. Изоляция Wi-Fi-клиентов, гостевая сеть, VLAN, VPN и фильтрация UDP 5353 могут мешать обнаружению. Попробуйте увеличить `--duration` или выбрать `--interface`.

Пустой список означает, что за время сканирования не получены выбранные объявления. Сведения публикуют сами устройства; запись не подтверждает их подлинность или доступность всех функций. Сканер не подключается к объявленным портам и не отправляет команды воспроизведения.

## Разработка и связь

Я использую pytest, Ruff и GitHub Actions. Команды проверок — в [docs/TESTING.md](docs/TESTING.md), изменения версий — в [CHANGELOG.md](CHANGELOG.md).

Об ошибках напишите мне в [Issues](https://github.com/Iversat/Alice-Discovery/issues). Перед публикацией отчёта удалите имена, адреса и идентификаторы домашних устройств. Для чувствительных сообщений см. [SECURITY.md](SECURITY.md).

Исследуйте собственную сеть либо получите разрешение её владельца. Правовой статус проекта описан в [LEGAL_NOTICE.md](LEGAL_NOTICE.md).
