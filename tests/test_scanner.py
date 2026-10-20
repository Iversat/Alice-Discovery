import ipaddress
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from zeroconf import ServiceInfo

import multiroom_scanner as scanner

TYPE = "_yandexio._tcp.local."
NAME = "Speaker." + TYPE


def make_info(name=NAME, port=1961, properties=None):
    return ServiceInfo(
        TYPE,
        name,
        addresses=[
            ipaddress.ip_address("192.0.2.10").packed,
            ipaddress.ip_address("2001:db8::1").packed,
        ],
        server="speaker.local.",
        port=port,
        properties=properties or {},
    )


def test_ipv4_ipv6_and_binary_txt():
    record = scanner.service_record(
        make_info(properties={b"model": b"speaker", b"binary": b"\xff", b"flag": None})
    )
    assert set(record["addresses"]) == {"192.0.2.10", "2001:db8::1"}
    assert record["properties"] == {"model": "speaker", "binary": "hex:ff", "flag": None}
    json.dumps(record)


def test_update_and_remove_use_full_service_name():
    listener = scanner.MyListener()
    zc = Mock()
    zc.get_service_info.return_value = make_info()
    listener.add_service(zc, TYPE, NAME)
    zc.get_service_info.return_value = make_info(port=9999)
    listener.update_service(zc, TYPE, NAME)
    assert listener.found_devices[NAME.casefold()]["port"] == 9999
    listener.remove_service(zc, TYPE, NAME.upper())
    assert listener.found_devices == {}


def test_multiple_services_on_same_host_are_not_lost():
    listener = scanner.MyListener()
    zc = Mock()
    for name in [NAME, "Other." + TYPE]:
        zc.get_service_info.return_value = make_info(name=name)
        listener.add_service(zc, TYPE, name)
    assert len(listener.found_devices) == 2
    listener.remove_service(zc, TYPE, NAME)
    assert len(listener.found_devices) == 1


def test_snapshot_cannot_mutate_listener():
    listener = scanner.MyListener()
    listener.add_service(Mock(get_service_info=Mock(return_value=make_info())), TYPE, NAME)
    snapshot = listener.found_devices
    snapshot[NAME.casefold()]["addresses"].clear()
    assert listener.found_devices[NAME.casefold()]["addresses"]


def test_missing_service_info_and_unknown_removal_are_safe():
    listener = scanner.MyListener()
    zc = Mock(get_service_info=Mock(return_value=None))
    listener.add_service(zc, TYPE, NAME)
    listener.remove_service(zc, TYPE, NAME)
    assert listener.found_devices == {}


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_duration_never_opens_network(monkeypatch, duration):
    zc = Mock()
    monkeypatch.setattr(scanner, "Zeroconf", zc)
    with pytest.raises(ValueError):
        scanner.scan_local_network_for_speakers(duration)
    zc.assert_not_called()


@pytest.mark.parametrize("types", [[], ["http"], ["_http._tcp.example."], ["_http._tcp.local.\n"]])
def test_invalid_service_types(types):
    with pytest.raises(ValueError):
        scanner.validate_service_types(types)


def test_types_are_normalized_and_deduplicated():
    assert scanner.validate_service_types([TYPE, TYPE.upper()]) == [TYPE]


@pytest.mark.parametrize("failure", [None, RuntimeError("browser failed"), KeyboardInterrupt()])
def test_resources_close_on_success_failure_and_interrupt(monkeypatch, failure):
    zc, browser = Mock(), Mock()
    monkeypatch.setattr(scanner, "Zeroconf", Mock(return_value=zc))
    monkeypatch.setattr(scanner, "ServiceBrowser", Mock(return_value=browser))
    monkeypatch.setattr(scanner.time, "sleep", Mock(side_effect=failure))
    if failure is None:
        assert scanner.scan_local_network_for_speakers(0.01) == []
    else:
        with pytest.raises(type(failure)):
            scanner.scan_local_network_for_speakers(0.01)
    browser.cancel.assert_called_once()
    zc.close.assert_called_once()


def test_browser_creation_failure_closes_zeroconf(monkeypatch):
    zc = Mock()
    monkeypatch.setattr(scanner, "Zeroconf", Mock(return_value=zc))
    monkeypatch.setattr(scanner, "ServiceBrowser", Mock(side_effect=RuntimeError("failed")))
    with pytest.raises(RuntimeError):
        scanner.scan_local_network_for_speakers()
    zc.close.assert_called_once()


def test_browser_cancel_failure_still_closes_zeroconf(monkeypatch):
    zc = Mock()
    browser = Mock(cancel=Mock(side_effect=RuntimeError("failed")))
    monkeypatch.setattr(scanner, "Zeroconf", Mock(return_value=zc))
    monkeypatch.setattr(scanner, "ServiceBrowser", Mock(return_value=browser))
    monkeypatch.setattr(scanner.time, "sleep", Mock())
    with pytest.raises(RuntimeError):
        scanner.scan_local_network_for_speakers()
    zc.close.assert_called_once()


def test_cli_json_has_no_progress_noise(monkeypatch, capsys):
    record = scanner.service_record(make_info())
    scan = Mock(return_value=[record])
    monkeypatch.setattr(scanner, "scan_local_network_for_speakers", scan)
    assert scanner.main(["--json", "--duration", "0.1", "--interface", "192.0.2.1"]) == 0
    assert json.loads(capsys.readouterr().out) == [record]
    scan.assert_called_once_with(0.1, None, ["192.0.2.1"])


def test_cli_network_error_goes_to_stderr(monkeypatch, capsys):
    monkeypatch.setattr(scanner, "scan_local_network_for_speakers", Mock(side_effect=OSError()))
    assert scanner.main(["--json"]) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "mDNS" in output.err


def test_cli_interrupt(monkeypatch):
    monkeypatch.setattr(
        scanner, "scan_local_network_for_speakers", Mock(side_effect=KeyboardInterrupt())
    )
    assert scanner.main([]) == 130


def test_fallback_name_without_server():
    info = SimpleNamespace(
        name=NAME, server=None, type=TYPE, port=1, properties={}, parsed_scoped_addresses=lambda: []
    )
    assert scanner.service_record(info)["name"] == "Speaker"
