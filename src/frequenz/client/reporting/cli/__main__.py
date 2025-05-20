# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Examples usage of reporting API."""

import argparse
import asyncio
from datetime import datetime, timedelta
from typing import AsyncIterator

from frequenz.client.common.metric import Metric

from frequenz.client.reporting import ReportingApiClient
from frequenz.client.reporting._types import MetricSample


def main() -> None:
    """Parse arguments and run the client."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        type=str,
        help="URL of the Reporting service",
        default="localhost:50051",
    )
    parser.add_argument(
        "--mid",
        type=int,
        help="Microgrid ID",
        required=True,
    )
    parser.add_argument(
        "--cid",
        nargs="+",
        type=str,
        help="Component IDs or formulae",
    )
    parser.add_argument(
        "--metrics",
        type=str,
        nargs="*",
        choices=[e.name for e in Metric],
        help="List of metrics to process",
        required=False,
        default=[],
    )
    parser.add_argument(
        "--states",
        action="store_true",
        help="Include states in the output",
    )
    parser.add_argument(
        "--bounds",
        action="store_true",
        help="Include bounds in the output",
    )
    parser.add_argument(
        "--start",
        type=datetime.fromisoformat,
        help="Start datetime in YYYY-MM-DDTHH:MM:SS format",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--end",
        type=datetime.fromisoformat,
        help="End datetime in YYYY-MM-DDTHH:MM:SS format",
        required=False,
        default=None,
    )
    parser.add_argument(
        "--resampling_period_s",
        type=int,
        help="Resampling period in seconds (integer, rounded to avoid subsecond precision issues).",
        default=None,
    )
    parser.add_argument("--psize", type=int, help="Page size", default=1000)
    parser.add_argument(
        "--format", choices=["iter", "csv", "dict"], help="Output format", default="csv"
    )
    parser.add_argument(
        "--key",
        type=str,
        help="API key",
        default=None,
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            microgrid_id=args.mid,
            component_id=args.cid,
            metric_names=args.metrics,
            start_time=args.start,
            end_time=args.end,
            resampling_period_s=args.resampling_period_s,
            states=args.states,
            bounds=args.bounds,
            service_address=args.url,
            key=args.key,
            fmt=args.format,
        )
    )


# pylint: disable=too-many-arguments, too-many-locals
async def run(  # noqa: DOC502
    *,
    microgrid_id: int,
    component_id: list[str],
    metric_names: list[str],
    start_time: datetime | None,
    end_time: datetime | None,
    resampling_period_s: int | None,
    states: bool,
    bounds: bool,
    service_address: str,
    key: str,
    fmt: str,
) -> None:
    """Test the ReportingApiClient.

    Args:
        microgrid_id: microgrid ID
        component_id: component ID
        metric_names: list of metric names
        start_time: start datetime, if None, the earliest available data will be used
        end_time: end datetime, if None starts streaming indefinitely from start_time
        resampling_period_s: The period for resampling the data.
        states: include states in the output
        bounds: include bounds in the output
        service_address: service address
        key: API key
        fmt: output format

    Raises:
        ValueError: if output format is invalid
    """
    client = ReportingApiClient(service_address, key)

    metrics = [Metric[mn] for mn in metric_names]

    cids = [int(cid.strip()) for cid in component_id if cid.strip().isdigit()]
    formulas = [cid.strip() for cid in component_id if not cid.strip().isdigit()]
    microgrid_components = [(microgrid_id, cids)]

    async def data_iter() -> AsyncIterator[MetricSample]:
        """Iterate over single metric.

        Just a wrapper around the client method for readability.

        Yields:
            Single metric samples
        """
        resampling_period = (
            timedelta(seconds=resampling_period_s)
            if resampling_period_s is not None
            else None
        )

        async for sample in client.receive_microgrid_components_data(
            microgrid_components=microgrid_components,
            metrics=metrics,
            start_time=start_time,
            end_time=end_time,
            resampling_period=resampling_period,
            include_states=states,
            include_bounds=bounds,
        ):
            yield sample

        for formula in formulas:
            assert resampling_period is not None
            for metric in metrics:
                async for sample in client.receive_aggregated_data(
                    microgrid_id=microgrid_id,
                    metric=metric,
                    aggregation_formula=formula,
                    start_time=start_time,
                    end_time=end_time,
                    resampling_period=resampling_period,
                ):
                    yield sample

    if fmt == "iter":
        # Iterate over single metric generator
        async for sample in data_iter():
            print(sample)

    elif fmt == "csv":
        # Print header
        print(",".join(MetricSample._fields))
        # Iterate over single metric generator and format as CSV
        async for sample in data_iter():
            print(",".join(str(e) for e in sample))

    else:
        raise ValueError(f"Invalid output format: {fmt}")

    return


if __name__ == "__main__":
    main()
