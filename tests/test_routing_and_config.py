"""Routing, config, and cross-cutting tests."""

from __future__ import annotations

import backend.config as config_module
from backend.config import load_config
from backend.handler import handler
from backend_test_helpers import make_http_event, parse_body


def test_unknown_route_returns_404(repo, config):
    event = make_http_event("DELETE", "/feedback", headers={})
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 404
    assert parse_body(resp)["error"]["code"] == "NOT_FOUND"


def test_unknown_path_returns_404(repo, config):
    event = make_http_event("GET", "/does-not-exist")
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 404


def test_post_to_health_returns_404(repo, config):
    event = make_http_event("POST", "/health")
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 404


def test_rest_v1_event_shape_supported(repo, config):
    # REST (v1) proxy event: httpMethod/path instead of requestContext.http.
    event = {"httpMethod": "GET", "path": "/health", "headers": {}}
    resp = handler(event, repo=repo, config=config)
    assert resp["statusCode"] == 200


def test_load_config_reads_environment(monkeypatch):
    monkeypatch.setenv(config_module.TABLE_NAME_ENV, "MyTable")
    monkeypatch.setenv(config_module.ORGANIZER_KEY_ENV, "the-key")
    cfg = load_config()
    assert cfg.table_name == "MyTable"
    assert cfg.organizer_key == "the-key"


def test_load_config_defaults_to_empty(monkeypatch):
    monkeypatch.delenv(config_module.TABLE_NAME_ENV, raising=False)
    monkeypatch.delenv(config_module.ORGANIZER_KEY_ENV, raising=False)
    cfg = load_config()
    assert cfg.table_name == ""
    assert cfg.organizer_key == ""


def test_lambda_handler_alias_exists():
    from backend.handler import lambda_handler

    assert lambda_handler is handler
