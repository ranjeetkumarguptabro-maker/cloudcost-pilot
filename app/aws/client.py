"""AWS client initialization, session management, and STS identity validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
    ProfileNotFound,
)

from app.logging_config import get_logger

if TYPE_CHECKING:
    from mypy_boto3_sts.client import STSClient

logger = get_logger(__name__)

# Standard Boto3 retry config: adaptive retry mode with exponential backoff
BOTO_CONFIG = Config(
    retries={
        "max_attempts": 5,
        "mode": "standard",
    },
)


class AWSAuthenticationError(Exception):
    """Raised when AWS credentials are missing, invalid, or expired."""


class AWSClientError(Exception):
    """Raised when an AWS API call fails."""


def get_boto3_session(
    profile_name: str | None = None,
    region_name: str | None = None,
) -> boto3.Session:
    """Create a boto3.Session using the specified profile and region.

    If profile_name is None, uses standard AWS credential provider chain
    (environment variables, IAM role, or default profile).

    Args:
        profile_name: Optional AWS CLI profile name.
        region_name: Optional AWS region name.

    Returns:
        boto3.Session instance.

    Raises:
        AWSAuthenticationError: If the specified profile does not exist.
    """
    try:
        session = boto3.Session(
            profile_name=profile_name,
            region_name=region_name,
        )
        return session
    except ProfileNotFound as exc:
        msg = (
            f"AWS profile '{profile_name}' was not found in ~/.aws/credentials or ~/.aws/config. "
            "Please run 'aws configure --profile <name>' or check your configuration."
        )
        logger.error(msg)
        raise AWSAuthenticationError(msg) from exc


def validate_aws_identity(session: boto3.Session) -> dict[str, str]:
    """Validate AWS credentials by calling STS GetCallerIdentity.

    Args:
        session: Active boto3.Session.

    Returns:
        Dictionary containing account_id, arn, and user_id.

    Raises:
        AWSAuthenticationError: If credentials are not configured or invalid.
        AWSClientError: If the STS API call fails.
    """
    try:
        sts_client: STSClient = session.client("sts", config=BOTO_CONFIG)  # type: ignore[assignment]
        identity = sts_client.get_caller_identity()

        account_id = identity.get("Account", "Unknown")
        arn = identity.get("Arn", "Unknown")
        user_id = identity.get("UserId", "Unknown")

        logger.info(
            "AWS credentials validated successfully. Connected as Account: %s, Identity ARN: %s",
            account_id,
            arn,
        )

        return {
            "account_id": str(account_id),
            "arn": str(arn),
            "user_id": str(user_id),
        }
    except NoCredentialsError as exc:
        msg = (
            "No AWS credentials found. Please configure credentials via 'aws configure', "
            "environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY), or an IAM role."
        )
        logger.error(msg)
        raise AWSAuthenticationError(msg) from exc
    except PartialCredentialsError as exc:
        msg = "Incomplete AWS credentials found. Both access key and secret key are required."
        logger.error(msg)
        raise AWSAuthenticationError(msg) from exc
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "Unknown")
        error_msg = exc.response.get("Error", {}).get("Message", str(exc))
        msg = f"Failed to authenticate with AWS STS [{error_code}]: {error_msg}"
        logger.error(msg)
        raise AWSAuthenticationError(msg) from exc
    except EndpointConnectionError as exc:
        msg = f"Network error connecting to AWS STS endpoint: {exc}"
        logger.error(msg)
        raise AWSClientError(msg) from exc


def create_cost_explorer_client(
    session: boto3.Session,
    region_name: str = "us-east-1",
) -> Any:
    """Create a Boto3 Cost Explorer client configured for us-east-1.

    AWS Cost Explorer is a global service whose endpoint is accessed in us-east-1.

    Args:
        session: Active boto3.Session.
        region_name: Cost Explorer endpoint region (defaults to us-east-1).

    Returns:
        Cost Explorer client instance.
    """
    return session.client("ce", region_name=region_name, config=BOTO_CONFIG)
