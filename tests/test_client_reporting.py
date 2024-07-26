# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Tests for the frequenz.client.reporting package."""
from unittest.mock import MagicMock, patch

import grpc.aio as grpcaio
import pytest
from frequenz.api.reporting.v1.reporting_pb2_grpc import ReportingStub
from frequenz.client.base.client import BaseApiClient

from frequenz.client.reporting import ReportingApiClient
from frequenz.client.reporting._client import ComponentsDataBatch


@pytest.mark.asyncio
async def test_client_initialization() -> None:
    """Test that the client initializes the BaseApiClient with grpcaio.Channel."""
    with patch.object(BaseApiClient, "__init__", return_value=None) as mock_base_init:
        client = ReportingApiClient("gprc://localhost:50051")  # noqa: F841
        mock_base_init.assert_called_once_with(
            "gprc://localhost:50051", ReportingStub, grpcaio.Channel
        )


def test_components_data_batch_is_empty_true() -> None:
    """Test that the is_empty method returns True when the page is empty."""
    data_pb = MagicMock()
    data_pb.components = []
    batch = ComponentsDataBatch(_data_pb=data_pb)
    assert batch.is_empty() is True


def test_components_data_batch_is_empty_false() -> None:
    """Test that the is_empty method returns False when the page is not empty."""
    data_pb = MagicMock()
    data_pb.components = [MagicMock()]
    data_pb.components[0].metric_samples = [MagicMock()]
    batch = ComponentsDataBatch(_data_pb=data_pb)
    assert batch.is_empty() is False
