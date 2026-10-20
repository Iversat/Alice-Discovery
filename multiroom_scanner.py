"""Discover services advertised by speakers on the local network via mDNS."""

from __future__ import annotations

import argparse
import copy
import json
import logging
import math
import re
import sys
import threading
import time
from collections.abc import Sequence
from typing import Any

from zeroconf import InterfaceChoice, ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

DEFAULT_SERVICE_TYPES = (
    "_yandexio._tcp.local.",
    "_yandexstation._tcp.local.",
    "_googlecast._tcp.local.",
    "_spotify-connect._tcp.local.",
)
LOGGER = logging.getLogger(__name__)


def decode_txt(value: bytes | str | None) -> str | None:
    """Keep undecodable TXT values lossless and JSON compatible."""
    if not isinstance(value, bytes):
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return "hex:" + value.hex()


def service_record(info: ServiceInfo) -> dict[str, Any]:
    """Convert IPv4/IPv6 addresses and TXT data into a serializable record."""
    return {
        "name": (info.server or info.name).split(".", 1)[0],
        "server": info.server,
        "service_name": info.name,
        "type": info.type,
        "addresses": sorted(set(info.parsed_scoped_addresses())),
        "port": info.port,
        "properties": {
            decode_txt(key): decode_txt(value) for key, value in info.properties.items()
        },
    }


class MyListener(ServiceListener):
    """Track service instances; callbacks run in the browser's worker thread."""

    def __init__(self) -> None:
        self._services: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @property
    def found_devices(self) -> dict[str, dict[str, Any]]:
        """Return a stable copy keyed by full service name, not by host name."""
        with self._lock:
            return copy.deepcopy(self._services)

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name, timeout=1000)
        if info is None:
            return
        record = service_record(info)
        with self._lock:
            self._services[name.casefold()] = record
        LOGGER.debug("Service updated: %s", name)

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        self.add_service(zc, type_, name)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        with self._lock:
            self._services.pop(name.casefold(), None)


def validate_duration(value: float) -> float:
    duration = float(value)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Длительность должна быть положительным конечным числом.")
    return duration


def validate_service_types(types: Sequence[str]) -> list[str]:
    if not types:
        raise ValueError("Укажите хотя бы один тип mDNS-сервиса.")
    result = []
    for value in types:
        if not re.fullmatch(r"_[a-z0-9-]+\._(?:tcp|udp)\.local\.", value, re.IGNORECASE):
            raise ValueError("Тип сервиса должен иметь вид _name._tcp.local. или _name._udp.local.")
        if value.lower() not in result:
            result.append(value.lower())
    return result


def scan_local_network_for_speakers(
    scan_duration_seconds: float = 10,
    service_types: Sequence[str] | None = None,
    interfaces: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return service advertisements seen during a bounded scan.

    This uses multicast DNS only. It does not connect to advertised ports,
    authenticate to accounts, or control playback.
    """
    duration = validate_duration(scan_duration_seconds)
    types = validate_service_types(
        DEFAULT_SERVICE_TYPES if service_types is None else service_types
    )
    listener = MyListener()
    zc = Zeroconf(interfaces=interfaces if interfaces is not None else InterfaceChoice.All)
    browser = None
    try:
        browser = ServiceBrowser(zc, types, listener=listener)
        time.sleep(duration)
    finally:
        try:
            if browser is not None:
                browser.cancel()
        finally:
            zc.close()
    return sorted(
        listener.found_devices.values(), key=lambda record: record["service_name"].casefold()
    )


def print_records(records: list[dict[str, Any]]) -> None:
    print(f"Найдено сервисов: {len(records)}")
    if not records:
        print("Устройства не объявляют выбранные сервисы или mDNS недоступен в этой сети.")
    for index, record in enumerate(records, 1):
        addresses = ", ".join(record["addresses"]) or "не объявлены"
        print(f"\n{index:02d}  {record['name']}")
        print(f"    Сервис   {record['type']}")
        print(f"    Адреса   {addresses}")
        print(f"    Порт     {record['port']}")
        print(f"    Имя      {record['service_name']}")
        print(f"    TXT      {json.dumps(record['properties'], ensure_ascii=False)}")


def main(argv: Sequence[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Поиск объявлений умных колонок через mDNS.")
    parser.add_argument(
        "--duration", type=float, default=10, metavar="SECONDS", help="длительность, 10 с"
    )
    parser.add_argument("--service", action="append", help="тип сервиса; можно повторить")
    parser.add_argument(
        "--interface", action="append", help="IP локального интерфейса; можно повторить"
    )
    parser.add_argument("--json", action="store_true", help="только JSON в stdout")
    parser.add_argument("--verbose", action="store_true", help="диагностика в stderr")
    args = parser.parse_args(argv)
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    try:
        records = scan_local_network_for_speakers(args.duration, args.service, args.interface)
    except ValueError as error:
        parser.error(str(error))
    except KeyboardInterrupt:
        print("Сканирование остановлено.", file=sys.stderr)
        return 130
    except OSError:
        print(
            "Не удалось открыть mDNS. Проверьте сетевой интерфейс и доступ к UDP 5353.",
            file=sys.stderr,
        )
        return 1
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    else:
        print_records(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
