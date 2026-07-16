import math

from app.binary.binary_reader import BinaryReader
from app.models.entropy_region import EntropyRegion


class EntropyAnalyzer:
    """Shannon entropy per byte block; classifications are descriptive only."""

    def __init__(
        self,
        block_size: int = 64 * 1024,
        low_threshold: float = 3.0,
        high_threshold: float = 5.5,
        very_high_threshold: float = 7.5,
    ) -> None:
        if block_size <= 0:
            raise ValueError("block_size must be greater than zero")
        if not 0 <= low_threshold <= high_threshold <= very_high_threshold <= 8:
            raise ValueError("entropy thresholds must be ordered within 0..8")
        self.block_size = block_size
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold
        self.very_high_threshold = very_high_threshold

    def analyze(self, reader: BinaryReader) -> list[EntropyRegion]:
        regions: list[EntropyRegion] = []
        for offset, chunk in reader.iter_chunks(self.block_size):
            entropy = self.calculate_entropy(chunk)
            regions.append(
                EntropyRegion(
                    offset=offset,
                    length=len(chunk),
                    entropy=entropy,
                    classification=self.classify(entropy),
                )
            )
        return regions

    @staticmethod
    def calculate_entropy(data: bytes) -> float:
        if not data:
            return 0.0
        counts = [0] * 256
        for byte in data:
            counts[byte] += 1
        size = len(data)
        return -sum(
            (count / size) * math.log2(count / size)
            for count in counts
            if count
        )

    def classify(self, entropy: float) -> str:
        if entropy < self.low_threshold:
            return "low"
        if entropy < self.high_threshold:
            return "moderate"
        if entropy < self.very_high_threshold:
            return "high"
        return "very_high"

    @staticmethod
    def weighted_average(regions: list[EntropyRegion]) -> float | None:
        total_length = sum(region.length for region in regions)
        if total_length == 0:
            return None
        return sum(
            region.entropy * region.length for region in regions
        ) / total_length
