# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Examples usage of reporting API."""

import argparse
import asyncio
from datetime import datetime
from pprint import pprint
from typing import AsyncIterator

from frequenz.client.common.metric import Metric

from frequenz.client.reporting import ReportingApiClient
from frequenz.client.reporting._client import MetricSample


def main() -> None:
    """Parse arguments and run the client."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url",
        type=str,
        help="URL of the Reporting service",
        default="localhost:50051",
    )
    parser.add_argument("--mid", type=int, help="Microgrid ID", required=True)
    parser.add_argument("--cid", type=int, help="Component ID", required=True)
    parser.add_argument(
        "--metrics",
        type=str,
        nargs="+",
        choices=[e.name for e in Metric],
        help="List of metrics to process",
        required=True,
    )
    parser.add_argument(
        "--start",
        type=datetime.fromisoformat,
        help="Start datetime in YYYY-MM-DDTHH:MM:SS format",
        required=True,
    )
    parser.add_argument(
        "--end",
        type=datetime.fromisoformat,
        help="End datetime in YYYY-MM-DDTHH:MM:SS format",
        required=True,
    )
    parser.add_argument("--resolution", type=int, help="Resolution", default=None)
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
            args.mid,
            args.cid,
            args.metrics,
            args.start,
            args.end,
            args.resolution,
            service_address=args.url,
            key=args.key,
            fmt=args.format,
        )
    )


# pylint: disable=too-many-arguments, too-many-locals
async def run(
    microgrid_id: int,
    component_id: int,
    metric_names: list[str],
    start_dt: datetime,
    end_dt: datetime,
    resolution: int,
    service_address: str,
    key: str,
    fmt: str,
) -> None:
    """Test the ReportingApiClient.

    Args:
        microgrid_id: microgrid ID
        component_id: component ID
        metric_names: list of metric names
        start_dt: start datetime
        end_dt: end datetime
        resolution: resampling resolution in sec
        service_address: service address
        key: API key
        fmt: output format

    Raises:
        ValueError: if output format is invalid
    """
    client = ReportingApiClient(service_address, key)

    metrics = [Metric[mn] for mn in metric_names]

    def data_iter() -> AsyncIterator[MetricSample]:
        """Iterate over single metric.

        Just a wrapper around the client method for readability.

        Returns:
            Iterator over single metric samples
        """
        return client.list_single_component_data(
            microgrid_id=microgrid_id,
            component_id=component_id,
            metrics=metrics,
            start_dt=start_dt,
            end_dt=end_dt,
            resolution=resolution,
        )

    if fmt == "iter":
        # Iterate over single metric generator
        async for sample in data_iter():
            print(sample)

    elif fmt == "dict":
        # Dumping all data as a single dict
        dct = await iter_to_dict(data_iter())
        pprint(dct)

    elif fmt == "csv":
        # Print header
        print(",".join(MetricSample._fields))
        # Iterate over single metric generator and format as CSV
        async for sample in data_iter():
            print(",".join(str(e) for e in sample))

    else:
        raise ValueError(f"Invalid output format: {fmt}")

    return


async def iter_to_dict(
    components_data_iter: AsyncIterator[MetricSample],
) -> dict[int, dict[int, dict[datetime, dict[Metric, float]]]]:
    """Convert components data iterator into a single dict.

        The nesting structure is:
        {
            microgrid_id: {
                component_id: {
                    timestamp: {
                        metric: value
                    }
                }
            }
        }

    Args:
        components_data_iter: async generator

    Returns:
        Single dict with with all components data
    """
    ret: dict[int, dict[int, dict[datetime, dict[Metric, float]]]] = {}

    async for ts, mid, cid, met, value in components_data_iter:
        if mid not in ret:
            ret[mid] = {}
        if cid not in ret[mid]:
            ret[mid][cid] = {}
        if ts not in ret[mid][cid]:
            ret[mid][cid][ts] = {}

        ret[mid][cid][ts][met] = value

    return ret


if __name__ == "__main__":
    main()
