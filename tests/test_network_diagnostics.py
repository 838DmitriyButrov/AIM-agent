"""Network failure regression tests: no real external sockets needed."""
import json
import socket
from pathlib import Path
import pytest
from siteaudit import crawler, network, cli
from siteaudit.orchestrator import run_audit
from siteaudit.report import to_markdown


def test_dns_temporary_not_misclassified_as_unsafe(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror(socket.EAI_AGAIN, 'Temporary failure in name resolution')
    monkeypatch.setattr(crawler.socket, 'getaddrinfo', fail)
    with pytest.raises(crawler.DNSResolutionError) as caught:
        crawler.validate_public_url('https://lenta.com/')
    assert caught.value.code == 'DNS_TEMPORARY'


def test_unknown_domain_distinguished_from_infrastructure(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror(socket.EAI_NONAME, 'Name or service not known')
    monkeypatch.setattr(crawler.socket, 'getaddrinfo', fail)
    with pytest.raises(crawler.DNSResolutionError) as caught:
        crawler.validate_public_url('https://typo.invalid/')
    assert caught.value.code == 'DNS_NOT_FOUND'


def test_failed_dns_yields_structured_no_audit_report(monkeypatch):
    monkeypatch.setattr(crawler.socket, 'getaddrinfo', lambda *args, **kwargs:
                        (_ for _ in ()).throw(socket.gaierror(socket.EAI_AGAIN, 'Temporary')))
    report = run_audit('https://metro-cc.ru/')
    assert report.pages_scanned == 0
    assert report.findings == []
    assert report.coverage['scan_status'] == 'blocked_network'
    assert report.coverage['error_code'] == 'DNS_TEMPORARY'
    markdown = to_markdown(report)
    assert 'Сканирование не началось' in markdown
    assert 'проблемой сайта' in markdown
    assert 'Автоматически проверяемых проблем не найдено' not in markdown


def test_cli_saves_failure_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(crawler.socket, 'getaddrinfo', lambda *args, **kwargs:
                        (_ for _ in ()).throw(socket.gaierror(socket.EAI_AGAIN, 'Temporary')))
    base = tmp_path / 'test'
    assert cli.main(['scan','https://lenta.com/', '--out', str(base)]) == 2
    data = json.loads(base.with_suffix('.json').read_text())
    assert data['coverage']['error_code'] == 'DNS_TEMPORARY'
    assert base.with_suffix('.md').exists()


def test_doctor_reports_dns_and_egress_without_bypass(monkeypatch):
    monkeypatch.setattr(network, 'validate_public_url', lambda url:
                        (_ for _ in ()).throw(crawler.DNSResolutionError('lenta.com', 'DNS_TEMPORARY')))
    def refused(*args, **kwargs):
        raise ConnectionRefusedError('denied')
    monkeypatch.setattr(network.socket, 'create_connection', refused)
    result = network.diagnose_network('https://lenta.com/')
    assert result['dns_status'] == 'DNS_TEMPORARY'
    assert 'blocked' in result['egress_status']
    assert 'sandbox' in result['diagnosis']


def test_doctor_rejects_private_target_without_probe(monkeypatch):
    def fail_probe(*args, **kwargs):
        raise AssertionError('must not probe')
    monkeypatch.setattr(network.socket, 'create_connection', fail_probe)
    with pytest.raises(crawler.UnsafeTarget):
        network.diagnose_network('http://127.0.0.1/')


def test_cli_preserves_dotted_output_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(crawler.socket, 'getaddrinfo', lambda *args, **kwargs:
                        (_ for _ in ()).throw(socket.gaierror(socket.EAI_AGAIN, 'Temporary')))
    base = tmp_path / 'retail-v0.2.1'
    assert cli.main(['scan','https://www.auchan.ru/', '--out', str(base)]) == 2
    assert (tmp_path / 'retail-v0.2.1.json').exists()
    assert (tmp_path / 'retail-v0.2.1.md').exists()
