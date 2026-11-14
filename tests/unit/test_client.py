"""Unit tests for AWS client initialization and STS identity validation."""

from __future__ import annotations

import boto3
import pytest
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from botocore.stub import Stubber

from app.aws.client import (
    AWSAuthenticationError,
    create_cost_explorer_client,
    get_boto3_session,
    validate_aws_identity,
)


def test_get_boto3_session_default():
    """Verify default session creation succeeds without error."""
    session = get_boto3_session()
    assert isinstance(session, boto3.Session)


def test_get_boto3_session_invalid_profile():
    """Verify requesting a non-existent AWS profile raises AWSAuthenticationError."""
    with pytest.raises(AWSAuthenticationError) as exc_info:
        get_boto3_session(profile_name="non-existent-profile-xyz-98765")
    assert "was not found" in str(exc_info.value)


def test_validate_aws_identity_success(mock_sts_response):
    """Verify validate_aws_identity successfully extracts Account ID and ARN."""
    session = boto3.Session(region_name="us-east-1")
    sts_client = session.client("sts")

    with Stubber(sts_client) as stubber:
        stubber.add_response("get_caller_identity", mock_sts_response)

        # Patch session.client to return stubbed client
        orig_client = session.client

        def mock_client(service_name, *args, **kwargs):
            if service_name == "sts":
                return sts_client
            return orig_client(service_name, *args, **kwargs)

        session.client = mock_client  # type: ignore[method-assign]

        identity = validate_aws_identity(session)

    assert identity["account_id"] == "123456789012"
    assert identity["arn"] == "arn:aws:sts::123456789012:assumed-role/CloudCostPilotRole/session"
    assert identity["user_id"] == "AROA123456789EXAMPLE:session-name"


def test_validate_aws_identity_no_credentials():
    """Verify NoCredentialsError raises a helpful AWSAuthenticationError."""
    session = boto3.Session(region_name="us-east-1")
    sts_client = session.client("sts")

    with Stubber(sts_client) as stubber:
        stubber.add_client_error(
            "get_caller_identity",
            service_error_code="AuthFailure",
            service_message="AWS was not able to validate the provided access credentials",
        )

        orig_client = session.client

        def mock_client(service_name, *args, **kwargs):
            if service_name == "sts":
                return sts_client
            return orig_client(service_name, *args, **kwargs)

        session.client = mock_client  # type: ignore[method-assign]

        with pytest.raises(AWSAuthenticationError) as exc_info:
            validate_aws_identity(session)

        assert "Failed to authenticate with AWS STS" in str(exc_info.value)


def test_validate_aws_identity_raises_no_credentials_error(mocker):
    """Verify NoCredentialsError from boto3 is caught and wrapped."""
    session = boto3.Session(region_name="us-east-1")
    mocker.patch.object(session, "client", side_effect=NoCredentialsError())

    with pytest.raises(AWSAuthenticationError) as exc_info:
        validate_aws_identity(session)

    assert "No AWS credentials found" in str(exc_info.value)


def test_validate_aws_identity_raises_partial_credentials_error(mocker):
    """Verify PartialCredentialsError from boto3 is caught and wrapped."""
    session = boto3.Session(region_name="us-east-1")
    mocker.patch.object(
        session,
        "client",
        side_effect=PartialCredentialsError(provider="env", cred_var="AWS_SECRET_ACCESS_KEY"),
    )

    with pytest.raises(AWSAuthenticationError) as exc_info:
        validate_aws_identity(session)

    assert "Incomplete AWS credentials found" in str(exc_info.value)


def test_create_cost_explorer_client():
    """Verify Cost Explorer client factory targets us-east-1 endpoint."""
    session = boto3.Session()
    ce = create_cost_explorer_client(session)
    assert ce.meta.endpoint_url == "https://ce.us-east-1.amazonaws.com"
    assert ce.meta.region_name in ("us-east-1", "aws-global")
