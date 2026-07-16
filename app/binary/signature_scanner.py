from app.binary.binary_reader import BinaryReader
from app.binary.signatures import BINARY_SIGNATURES
from app.models.binary_region import BinaryRegion


class SignatureScanner:
    SIGNATURES = BINARY_SIGNATURES

    def scan(
        self,
        reader: BinaryReader,
        max_results_per_signature: int = 100,
    ) -> list[BinaryRegion]:
        if max_results_per_signature <= 0:
            raise ValueError(
                "max_results_per_signature must be greater than zero"
            )
        regions: list[BinaryRegion] = []
        for format_name, signature in self.SIGNATURES.items():
            for offset in reader.find_bytes(
                signature, max_results=max_results_per_signature
            ):
                internal = offset != 0
                kind = f"candidate_{format_name}" if internal else format_name
                location = "região interna" if internal else "início"
                regions.append(
                    BinaryRegion(
                        offset=offset,
                        length=None,
                        kind=kind,
                        signature=signature.hex().upper(),
                        description=(
                            f"Assinatura {format_name.upper()} localizada no "
                            f"{location} do arquivo."
                        ),
                        status="candidate" if internal else "recognized",
                    )
                )
        return sorted(regions, key=lambda region: region.offset)
