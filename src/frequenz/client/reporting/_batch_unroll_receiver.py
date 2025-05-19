# License: MIT
# Copyright © 2024 Frequenz Energy-as-a-Service GmbH

"""A receiver that unrolls batches of data into individual samples."""

from collections.abc import Iterator

from frequenz.channels import Receiver, ReceiverStoppedError
from typing_extensions import override

from ._types import ComponentsDataBatch, MetricSample


class BatchUnrollReceiver(Receiver[MetricSample]):
    """Receiver to unroll `ComponentsDataBatch`s into `MetricSample`s."""

    def __init__(self, stream: Receiver[ComponentsDataBatch]) -> None:
        """Initialize the receiver.

        Args:
            stream: The stream to receive batches from.
        """
        self._stream: Receiver[ComponentsDataBatch] = stream
        self._batch_iter: Iterator[MetricSample] | None = None
        self._latest_sample: MetricSample | None = None
        self._no_more_data: bool = False

    @override
    async def ready(self) -> bool:
        """Wait until the next `MetricSample` is ready."""
        # If ready is called multiple times, we should return the same result
        # so we don't loose any data
        if self._latest_sample is not None:
            return True

        while True:
            # If we have a batch iterator, try to get the next sample
            if self._batch_iter is not None:
                try:
                    self._latest_sample = next(self._batch_iter)
                    return True
                # If the batch is done, set the batch iterator to None
                except StopIteration:
                    self._batch_iter = None

            # If we don't have a batch iterator, try to get the next batch
            try:
                batch = await anext(self._stream)
                self._batch_iter = iter(batch)
            # If the stream is done, return False
            except StopAsyncIteration:
                self._no_more_data = True
                return False

    @override
    def consume(self) -> MetricSample:
        """Consume the next `MetricSample`.

        Returns:
            The next `MetricSample`.

        Raises:
            ReceiverStoppedError: If the receiver is stopped.
            RuntimeError: If the receiver is not ready.
        """
        sample = self._latest_sample
        if sample is None:
            if self._no_more_data:
                raise ReceiverStoppedError(self)
            raise RuntimeError("consume called before ready")
        self._latest_sample = None
        return sample
