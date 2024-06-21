# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Client for requests to the Reporting API."""

from collections import namedtuple
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import grpc
import grpc.aio as grpcaio

# pylint: disable=no-name-in-module
from frequenz.api.common.v1.microgrid.microgrid_pb2 import (
    MicrogridComponentIDs as PBMicrogridComponentIDs,
)
from frequenz.api.reporting.v1.reporting_pb2 import (
    ReceiveMicrogridComponentsDataStreamRequest as PBReceiveMicrogridComponentsDataStreamRequest,
)
from frequenz.api.reporting.v1.reporting_pb2 import (
    ReceiveMicrogridComponentsDataStreamResponse as PBReceiveMicrogridComponentsDataStreamResponse,
)
from frequenz.api.reporting.v1.reporting_pb2 import (
    ResamplingOptions as PBResamplingOptions,
)
from frequenz.api.reporting.v1.reporting_pb2 import TimeFilter as PBTimeFilter
from frequenz.api.reporting.v1.reporting_pb2_grpc import ReportingStub
from frequenz.client.common.metric import Metric
from google.protobuf.timestamp_pb2 import Timestamp as PBTimestamp

# pylint: enable=no-name-in-module

MetricSample = namedtuple(
    "MetricSample", ["timestamp", "microgrid_id", "component_id", "metric", "value"]
)
"""Type for a sample of a time series incl. metric type, microgrid and component ID

A named tuple was chosen to allow safe access to the fields while keeping the
simplicity of a tuple. This data type can be easily used to create a numpy array
or a pandas DataFrame.
"""


@dataclass(frozen=True)
class ComponentsDataBatch:
    """A batch of components data for a single microgrid returned by the Reporting service."""

    _data_pb: PBReceiveMicrogridComponentsDataStreamResponse
    """The underlying protobuf message."""

    def is_empty(self) -> bool:
        """Check if the batch contains valid data.

        Returns:
            True if the batch contains no valid data.
        """
        if not self._data_pb.components:
            return True
        if not self._data_pb.components[0].metric_samples:
            return True
        return False

    def __iter__(self) -> Iterator[MetricSample]:
        """Get generator that iterates over all values in the batch.

        Note: So far only `SimpleMetricSample` in the `MetricSampleVariant`
        message is supported.


        Yields:
            A named tuple with the following fields:
            * timestamp: The timestamp of the metric sample.
            * microgrid_id: The microgrid ID.
            * component_id: The component ID.
            * metric: The metric name.
            * value: The metric value.
        """
        data = self._data_pb
        mid = data.microgrid_id
        for cdata in data.components:
            cid = cdata.component_id
            for msample in cdata.metric_samples:
                ts = msample.sampled_at.ToDatetime()
                met = Metric.from_proto(msample.metric).name
                value = (
                    msample.value.simple_metric.value
                    if msample.value.simple_metric
                    else None
                )
                yield MetricSample(
                    timestamp=ts,
                    microgrid_id=mid,
                    component_id=cid,
                    metric=met,
                    value=value,
                )


class ReportingApiClient:
    """A client for the Reporting service."""

    def __init__(self, service_address: str, key: str | None = None) -> None:
        """Create a new Reporting client.

        Args:
            service_address: The address of the Reporting service.
            key: The API key for the authorization.
        """
        self._grpc_channel = grpcaio.secure_channel(
            service_address, grpc.ssl_channel_credentials()
        )
        self._stub = ReportingStub(self._grpc_channel)
        self._metadata = (("key", key),) if key else ()

    # pylint: disable=too-many-arguments
    async def list_single_component_data(
        self,
        *,
        microgrid_id: int,
        component_id: int,
        metrics: Metric | list[Metric],
        start_dt: datetime,
        end_dt: datetime,
        resolution: int | None,
    ) -> AsyncIterator[MetricSample]:
        """Iterate over the data for a single metric.

        Args:
            microgrid_id: The microgrid ID.
            component_id: The component ID.
            metrics: The metric name or list of metric names.
            start_dt: The start date and time.
            end_dt: The end date and time.
            resolution: The resampling resolution for the data, represented in seconds.

        Yields:
            A named tuple with the following fields:
            * timestamp: The timestamp of the metric sample.
            * value: The metric value.
        """
        async for batch in self._list_microgrid_components_data_batch(
            microgrid_components=[(microgrid_id, [component_id])],
            metrics=[metrics] if isinstance(metrics, Metric) else metrics,
            start_dt=start_dt,
            end_dt=end_dt,
            resolution=resolution,
        ):
            for entry in batch:
                yield entry

    # pylint: disable=too-many-arguments
    async def list_microgrid_components_data(
        self,
        *,
        microgrid_components: list[tuple[int, list[int]]],
        metrics: Metric | list[Metric],
        start_dt: datetime,
        end_dt: datetime,
        resolution: int | None,
    ) -> AsyncIterator[MetricSample]:
        """Iterate over the data for multiple microgrids and components.

        Args:
            microgrid_components: List of tuples where each tuple contains
                                  microgrid ID and corresponding component IDs.
            metrics: The metric name or list of metric names.
            start_dt: The start date and time.
            end_dt: The end date and time.
            resolution: The resampling resolution for the data, represented in seconds.

        Yields:
            A named tuple with the following fields:
            * microgrid_id: The microgrid ID.
            * component_id: The component ID.
            * metric: The metric name.
            * timestamp: The timestamp of the metric sample.
            * value: The metric value.
        """
        async for batch in self._list_microgrid_components_data_batch(
            microgrid_components=microgrid_components,
            metrics=[metrics] if isinstance(metrics, Metric) else metrics,
            start_dt=start_dt,
            end_dt=end_dt,
            resolution=resolution,
        ):
            for entry in batch:
                yield entry

    # pylint: disable=too-many-arguments
    async def _list_microgrid_components_data_batch(
        self,
        *,
        microgrid_components: list[tuple[int, list[int]]],
        metrics: list[Metric],
        start_dt: datetime,
        end_dt: datetime,
        resolution: int | None,
    ) -> AsyncIterator[ComponentsDataBatch]:
        """Iterate over the component data batches in the stream.

        Note: This does not yet support aggregating the data. It
        also does not yet support fetching bound and state data.

        Args:
            microgrid_components: A list of tuples of microgrid IDs and component IDs.
            metrics: A list of metrics.
            start_dt: The start date and time.
            end_dt: The end date and time.
            resolution: The resampling resolution for the data, represented in seconds.

        Yields:
            A ComponentsDataBatch object of microgrid components data.
        """
        microgrid_components_pb = [
            PBMicrogridComponentIDs(microgrid_id=mid, component_ids=cids)
            for mid, cids in microgrid_components
        ]

        def dt2ts(dt: datetime) -> PBTimestamp:
            ts = PBTimestamp()
            ts.FromDatetime(dt)
            return ts

        time_filter = PBTimeFilter(
            start=dt2ts(start_dt),
            end=dt2ts(end_dt),
        )

        list_filter = PBReceiveMicrogridComponentsDataStreamRequest.StreamFilter(
            time_filter=time_filter,
            resampling_options=PBResamplingOptions(resolution=resolution),
        )

        metrics_pb = [metric.to_proto() for metric in metrics]

        request = PBReceiveMicrogridComponentsDataStreamRequest(
            microgrid_components=microgrid_components_pb,
            metrics=metrics_pb,
            filter=list_filter,
        )

        try:
            stream = cast(
                AsyncIterator[PBReceiveMicrogridComponentsDataStreamResponse],
                self._stub.ReceiveMicrogridComponentsDataStream(
                    request, metadata=self._metadata
                ),
            )
            # grpc.aio is missing types and mypy thinks this is not
            # async iterable, but it is.
            async for response in stream:
                if not response:
                    break

                yield ComponentsDataBatch(response)

        except grpcaio.AioRpcError as e:
            print(f"RPC failed: {e}")
            return

    async def close(self) -> None:
        """Close the client and cancel any pending requests immediately."""
        await self._grpc_channel.close(grace=None)

    async def __aenter__(self) -> "ReportingApiClient":
        """Enter the async context."""
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: Any | None,
    ) -> bool | None:
        """
        Exit the asynchronous context manager.

        Note that exceptions are not handled here, but are allowed to propagate.

        Args:
            _exc_type: Type of exception raised in the async context.
            _exc_val: Exception instance raised.
            _exc_tb: Traceback object at the point where the exception occurred.

        Returns:
            None, allowing any exceptions to propagate.
        """
        await self.close()
        return None
