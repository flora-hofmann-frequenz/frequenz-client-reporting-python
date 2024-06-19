# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Tests for the frequenz.client.reporting package."""
from typing import Generator
from unittest.mock import ANY, MagicMock, patch

import pytest

from frequenz.client.reporting import ReportingApiClient
from frequenz.client.reporting._client import ComponentsDataBatch


@pytest.fixture
def mock_channel() -> Generator[MagicMock, None, None]:
    """Fixture for grpc.aio.secure_channel."""
    with patch("grpc.aio.secure_channel") as mock:
        yield mock


@pytest.mark.asyncio
async def test_client_initialization(mock_channel: MagicMock) -> None:
    """Test that the client initializes the channel."""
    client = ReportingApiClient("localhost:50051")  # noqa: F841
    mock_channel.assert_called_once_with("localhost:50051", ANY)


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
