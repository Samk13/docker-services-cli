# SPDX-FileCopyrightText: 2026 KTH Royal Institute of Technology.
# SPDX-License-Identifier: MIT

"""RustFS initialization tests."""

from unittest.mock import Mock

import botocore.session
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from docker_services_cli import services
from docker_services_cli.config import RUSTFS


@pytest.fixture()
def s3_client(monkeypatch):
    """Return an S3 client without using environment credentials or the network."""
    client = botocore.session.get_session().create_client(
        "s3",
        endpoint_url="http://localhost:9000",
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test-secret",
    )
    monkeypatch.setattr(services, "_rustfs_s3_client", lambda: client)
    monkeypatch.delenv("S3_CORS_ALLOWED_ORIGINS", raising=False)
    return client


def _expect_missing_cors(stubber, bucket="default"):
    """Expect a bucket without a CORS policy."""
    stubber.add_client_error(
        "get_bucket_cors",
        service_error_code="NoSuchCORSConfiguration",
        http_status_code=404,
        expected_params={"Bucket": bucket},
    )


def _cors_configuration(origins):
    """Return the expected local-development policy."""
    return {
        "CORSRules": [
            {
                "AllowedOrigins": origins,
                "AllowedMethods": ["GET", "HEAD", "PUT", "POST", "DELETE"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }


@pytest.mark.parametrize("bucket", ["default", "custom"])
def test_rustfs_initializes_bucket_cors(s3_client, bucket):
    """Initialize browser uploads for a bucket without a CORS policy."""
    with Stubber(s3_client) as stubber:
        stubber.add_response("create_bucket", {}, {"Bucket": bucket})
        _expect_missing_cors(stubber, bucket)
        stubber.add_response(
            "put_bucket_cors",
            {},
            {
                "Bucket": bucket,
                "CORSConfiguration": _cors_configuration(
                    RUSTFS["CORS_ALLOWED_ORIGINS"].split(",")
                ),
            },
        )
        assert services.rustfs_create_default_bucket(bucket=bucket)
        stubber.assert_no_pending_responses()


def test_rustfs_custom_cors_origins(s3_client, monkeypatch):
    """Read comma-separated origins from the environment."""
    monkeypatch.setenv(
        "S3_CORS_ALLOWED_ORIGINS", " https://example.org , , https://example.org:5000 "
    )
    with Stubber(s3_client) as stubber:
        stubber.add_response("create_bucket", {}, {"Bucket": "default"})
        _expect_missing_cors(stubber)
        stubber.add_response(
            "put_bucket_cors",
            {},
            {
                "Bucket": "default",
                "CORSConfiguration": _cors_configuration(
                    ["https://example.org", "https://example.org:5000"]
                ),
            },
        )
        assert services.rustfs_create_default_bucket()
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize("origins", ["", " , "])
def test_rustfs_cors_disabled(s3_client, monkeypatch, origins):
    """Allow opting out without reading or modifying the bucket policy."""
    monkeypatch.setenv("S3_CORS_ALLOWED_ORIGINS", origins)
    with Stubber(s3_client) as stubber:
        stubber.add_response("create_bucket", {}, {"Bucket": "default"})
        assert services.rustfs_create_default_bucket()
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize("create_error", [None, "BucketAlreadyOwnedByYou"])
def test_rustfs_preserves_existing_cors(s3_client, create_error):
    """Leave existing policies untouched, including on repeated initialization."""
    policy = {
        "CORSRules": [
            {"AllowedOrigins": ["https://example.org"], "AllowedMethods": ["GET"]}
        ]
    }
    with Stubber(s3_client) as stubber:
        if create_error:
            stubber.add_client_error(
                "create_bucket",
                service_error_code=create_error,
                http_status_code=409,
                expected_params={"Bucket": "default"},
            )
        else:
            stubber.add_response("create_bucket", {}, {"Bucket": "default"})
        stubber.add_response("get_bucket_cors", policy, {"Bucket": "default"})
        assert services.rustfs_create_default_bucket()
        stubber.assert_no_pending_responses()


def test_rustfs_repeated_initialization(s3_client):
    """Repeated initialization succeeds without rewriting the installed policy."""
    policy = _cors_configuration(RUSTFS["CORS_ALLOWED_ORIGINS"].split(","))
    with Stubber(s3_client) as stubber:
        stubber.add_response("create_bucket", {}, {"Bucket": "default"})
        _expect_missing_cors(stubber)
        stubber.add_response(
            "put_bucket_cors", {}, {"Bucket": "default", "CORSConfiguration": policy}
        )
        # AWS reports an existing owned bucket; RustFS returns success instead.
        stubber.add_client_error(
            "create_bucket",
            service_error_code="BucketAlreadyOwnedByYou",
            http_status_code=409,
            expected_params={"Bucket": "default"},
        )
        stubber.add_response("get_bucket_cors", policy, {"Bucket": "default"})
        assert services.rustfs_create_default_bucket()
        assert services.rustfs_create_default_bucket()
        stubber.assert_no_pending_responses()


def test_rustfs_bucket_owned_by_another_account(s3_client):
    """A bucket name collision must not be treated as successful initialization."""
    with Stubber(s3_client) as stubber:
        stubber.add_client_error(
            "create_bucket",
            service_error_code="BucketAlreadyExists",
            http_status_code=409,
            expected_params={"Bucket": "default"},
        )
        assert not services.rustfs_create_default_bucket()
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize(
    "operation", ["create_bucket", "get_bucket_cors", "put_bucket_cors"]
)
def test_rustfs_initialization_errors(s3_client, capsys, operation):
    """Report initialization errors rather than treating them as readiness."""
    with Stubber(s3_client) as stubber:
        if operation != "create_bucket":
            stubber.add_response("create_bucket", {}, {"Bucket": "default"})
        if operation == "put_bucket_cors":
            _expect_missing_cors(stubber)
        stubber.add_client_error(
            operation, service_error_code="AccessDenied", http_status_code=403
        )
        assert not services.rustfs_create_default_bucket(verbose=True)
        message = (
            "Could not create default bucket"
            if operation == "create_bucket"
            else "Could not configure default bucket CORS"
        )
        assert message in capsys.readouterr().out
        stubber.assert_no_pending_responses()


def test_rustfs_connection_error(s3_client, monkeypatch):
    """Return false on connection errors so the healthcheck can retry."""
    monkeypatch.setattr(
        s3_client,
        "create_bucket",
        Mock(side_effect=EndpointConnectionError(endpoint_url="http://localhost:9000")),
    )
    assert not services.rustfs_create_default_bucket()


@pytest.mark.parametrize("healthy", [True, False])
def test_rustfs_healthcheck_initialization(monkeypatch, healthy):
    """Initialize the default bucket only after the HTTP healthcheck succeeds."""
    monkeypatch.setattr(services, "_run_healthcheck_command", lambda *args: healthy)
    initialize = Mock(return_value=True)
    monkeypatch.setattr(services, "rustfs_create_default_bucket", initialize)
    assert services.rustfs_healthcheck(verbose=False) is healthy
    if healthy:
        initialize.assert_called_once_with(verbose=False)
    else:
        initialize.assert_not_called()


def test_rustfs_healthcheck_initialization_failure(monkeypatch):
    """Do not report readiness when bucket initialization fails."""
    monkeypatch.setattr(services, "_run_healthcheck_command", lambda *args: True)
    monkeypatch.setattr(
        services, "rustfs_create_default_bucket", lambda **kwargs: False
    )
    assert not services.rustfs_healthcheck(verbose=False)
