# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Client for requests to the Reporting API."""

from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator, Awaitable, Iterator, Type, cast

import grpc.aio as grpcaio

# pylint: disable=no-name-in-module
from frequenz.api.common.v1.metrics.metric_sample_pb2 import Metric as PBMetric
from frequenz.api.common.v1.microgrid.microgrid_pb2 import (
    MicrogridComponentIDs as PBMicrogridComponentIDs,
)
from frequenz.api.common.v1.pagination.pagination_params_pb2 import (
    PaginationParams as PBPaginationParams,
)
from frequenz.api.reporting.v1.reporting_pb2 import (
    ListMicrogridComponentsDataRequest as PBListMicrogridComponentsDataRequest,
)
from frequenz.api.reporting.v1.reporting_pb2 import (
    ListMicrogridComponentsDataResponse as PBListMicrogridComponentsDataResponse,
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
class ComponentsDataPage:
    """A page of microgrid components data returned by the Reporting service."""

    _data_pb: PBListMicrogridComponentsDataResponse
    """The underlying protobuf message."""

    def is_empty(self) -> bool:
        """Check if the page contains valid data.

        Returns:
            True if the page contains no valid data.
        """
        if not self._data_pb.microgrids:
            return True
        if not self._data_pb.microgrids[0].components:
            return True
        if not self._data_pb.microgrids[0].components[0].metric_samples:
            return True
        return False

    def __iter__(self) -> Iterator[MetricSample]:
        """Get generator that iterates over all values in the page.

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
        for mdata in data.microgrids:
            mid = mdata.microgrid_id
            for cdata in mdata.components:
                cid = cdata.component_id
                for msample in cdata.metric_samples:
                    ts = msample.sampled_at.ToDatetime()
                    met = Metric.from_proto(msample.metric).name
                    value = (
                        msample.sample.simple_metric.value
                        if msample.sample.simple_metric
                        else None
                    )
                    yield MetricSample(
                        timestamp=ts,
                        microgrid_id=mid,
                        component_id=cid,
                        metric=met,
                        value=value,
                    )

    @property
    def next_page_token(self) -> str | None:
        """Get the token for the next page of data.

        Returns:
            The token for the next page of data.
        """
        return self._data_pb.pagination_info.next_page_token


class ReportingApiClient:
    """A client for the Reporting service."""

    def __init__(self, service_address: str):
        """Create a new Reporting client.

        Args:
            service_address: The address of the Reporting service.
        """
        self._grpc_channel = grpcaio.insecure_channel(service_address)
        self._stub = ReportingStub(self._grpc_channel)

    # pylint: disable=too-many-arguments
    async def list_single_component_data(
        self,
        *,
        microgrid_id: int,
        component_id: int,
        metrics: Metric | list[Metric],
        start_dt: datetime,
        end_dt: datetime,
        page_size: int = 1000,
    ) -> AsyncIterator[MetricSample]:
        """Iterate over the data for a single metric.

        Args:
            microgrid_id: The microgrid ID.
            component_id: The component ID.
            metrics: The metric name or list of metric names.
            start_dt: The start date and time.
            end_dt: The end date and time.
            page_size: The page size.

        Yields:
            A named tuple with the following fields:
            * timestamp: The timestamp of the metric sample.
            * value: The metric value.
        """
        async for page in self._list_microgrid_components_data_pages(
            microgrid_components=[(microgrid_id, [component_id])],
            metrics=[metrics] if isinstance(metrics, Metric) else metrics,
            start_dt=start_dt,
            end_dt=end_dt,
            page_size=page_size,
        ):
            for entry in page:
                yield entry

    # pylint: disable=too-many-arguments
    async def list_microgrid_components_data(
        self,
        *,
        microgrid_components: list[tuple[int, list[int]]],
        metrics: Metric | list[Metric],
        start_dt: datetime,
        end_dt: datetime,
        page_size: int = 1000,
    ) -> AsyncIterator[MetricSample]:
        """Iterate over the data for multiple microgrids and components.

        Args:
            microgrid_components: List of tuples where each tuple contains
                                  microgrid ID and corresponding component IDs.
            metrics: The metric name or list of metric names.
            start_dt: The start date and time.
            end_dt: The end date and time.
            page_size: The page size.

        Yields:
            A named tuple with the following fields:
            * microgrid_id: The microgrid ID.
            * component_id: The component ID.
            * metric: The metric name.
            * timestamp: The timestamp of the metric sample.
            * value: The metric value.
        """
        async for page in self._list_microgrid_components_data_pages(
            microgrid_components=microgrid_components,
            metrics=[metrics] if isinstance(metrics, Metric) else metrics,
            start_dt=start_dt,
            end_dt=end_dt,
            page_size=page_size,
        ):
            for entry in page:
                yield entry

    # pylint: disable=too-many-arguments
    async def _list_microgrid_components_data_pages(
        self,
        *,
        microgrid_components: list[tuple[int, list[int]]],
        metrics: list[Metric],
        start_dt: datetime,
        end_dt: datetime,
        page_size: int = 1000,
    ) -> AsyncIterator[ComponentsDataPage]:
        """Iterate over the pages of microgrid components data.

        Note: This does not yet support resampling or aggregating the data. It
        also does not yet support fetching bound and state data.

        Args:
            microgrid_components: A list of tuples of microgrid IDs and component IDs.
            metrics: A list of metrics.
            start_dt: The start date and time.
            end_dt: The end date and time.
            page_size: The page size.

        Yields:
            A ComponentsDataPage object of microgrid components data.
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

        list_filter = PBListMicrogridComponentsDataRequest.ListFilter(
            time_filter=time_filter,
        )

        metrics_pb = [metric.to_proto() for metric in metrics]

        page_token = None

        while True:
            pagination_params = PBPaginationParams(
                page_size=page_size, page_token=page_token
            )

            response = await self._fetch_page(
                microgrid_components=microgrid_components_pb,
                metrics=metrics_pb,
                list_filter=list_filter,
                pagination_params=pagination_params,
            )
            if not response or response.is_empty():
                break

            yield response

            page_token = response.next_page_token
            if not page_token:
                break

    async def _fetch_page(
        self,
        *,
        microgrid_components: list[PBMicrogridComponentIDs],
        metrics: list[PBMetric.ValueType],
        list_filter: PBListMicrogridComponentsDataRequest.ListFilter,
        pagination_params: PBPaginationParams,
    ) -> ComponentsDataPage | None:
        """Fetch a single page of microgrid components data.

        Args:
            microgrid_components: A list of microgrid components.
            metrics: A list of metrics.
            list_filter: A list filter.
            pagination_params: A pagination params.

        Returns:
            A ComponentsDataPage object of microgrid components data.
        """
        try:
            request = PBListMicrogridComponentsDataRequest(
                microgrid_components=microgrid_components,
                metrics=metrics,
                filter=list_filter,
                pagination_params=pagination_params,
            )
            response = await cast(
                Awaitable[PBListMicrogridComponentsDataResponse],
                self._stub.ListMicrogridComponentsData(request),
            )
        except grpcaio.AioRpcError as e:
            print(f"RPC failed: {e}")
            return None
        return ComponentsDataPage(response)

    async def close(self) -> None:
        """Close the client and cancel any pending requests immediately."""
        await self._grpc_channel.close(grace=None)

    async def __aenter__(self) -> "ReportingApiClient":
        """Enter the async context."""
        return self

    async def __aexit__(
        self,
        _exc_type: Type[BaseException] | None,
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
