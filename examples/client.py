# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""Examples usage of reporting API."""

import argparse
import asyncio
from datetime import datetime
from pprint import pprint
from typing import AsyncIterator

import pandas as pd
from frequenz.client.common.metric import Metric

from frequenz.client.reporting import ReportingApiClient

# Experimental import
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
    parser.add_argument("--psize", type=int, help="Page size", default=100)
    parser.add_argument(
        "--display", choices=["iter", "df", "dict"], help="Display format", default="df"
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            args.mid,
            args.cid,
            args.metrics,
            args.start,
            args.end,
            page_size=args.psize,
            service_address=args.url,
            display=args.display,
        )
    )


# pylint: disable=too-many-arguments
async def run(
    microgrid_id: int,
    component_id: int,
    metric_names: list[str],
    start_dt: datetime,
    end_dt: datetime,
    page_size: int,
    service_address: str,
    display: str,
) -> None:
    """Test the ReportingApiClient.

    Args:
        microgrid_id: microgrid ID
        component_id: component ID
        metric_names: list of metric names
        start_dt: start datetime
        end_dt: end datetime
        page_size: page size
        service_address: service address
        display: display format

    Raises:
        ValueError: if display format is invalid
    """
    client = ReportingApiClient(service_address)

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
            page_size=page_size,
        )

    if display == "iter":
        print("########################################################")
        print("Iterate over single metric generator")
        async for sample in data_iter():
            print(sample)

    elif display == "dict":
        print("########################################################")
        print("Dumping all data as a single dict")
        dct = await iter_to_dict(data_iter())
        pprint(dct)

    elif display == "df":
        print("########################################################")
        print("Turn data into a pandas DataFrame")
        data = [cd async for cd in data_iter()]
        df = pd.DataFrame(data).set_index("timestamp")
        # Set option to display all rows
        pd.set_option("display.max_rows", None)
        pprint(df)

    else:
        raise ValueError(f"Invalid display format: {display}")

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
