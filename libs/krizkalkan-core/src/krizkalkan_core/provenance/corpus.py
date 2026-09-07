"""Köken referans korpusu — tarih damgalı geçmiş içerik kayıtları.

Gerçek sistemde bu korpus açık lisanslı afet haber videolarından ve DMM
bültenlerinde "yalanlanan görsel" olarak geçen içeriklerden FAISS indeksine
yüklenir. Bu sürümde aynı şema, tohumlanmış kayıtlarla doldurulmuştur.
"""

from __future__ import annotations

from dataclasses import dataclass

from krizkalkan_core.provenance.hashing import perceptual_hash


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    """İndekste tutulan tek bir referans kayıt."""

    corpus_id: str
    fingerprint: str
    first_published: str
    source: str
    event: str
    location: str
    frame_label: str

    @property
    def phash(self) -> int:
        return perceptual_hash(self.fingerprint)


#: Tohumlanmış referans korpusu. Demo senaryoları bu kayıtlarla eşleşir.
ENTRIES: list[CorpusEntry] = [
    CorpusEntry(
        corpus_id="KRP-2023-0208-014",
        fingerprint="deprem-yikim-hatay-2023",
        first_published="08.02.2023",
        source="Ulusal haber ajansı arşivi",
        event="6 Şubat 2023 Kahramanmaraş depremleri",
        location="Hatay",
        frame_label="00:04 · yıkılmış yapı cephesi",
    ),
    CorpusEntry(
        corpus_id="KRP-2023-0212-077",
        fingerprint="arama-kurtarma-kahramanmaras-2023",
        first_published="12.02.2023",
        source="Kurumsal basın arşivi",
        event="6 Şubat 2023 Kahramanmaraş depremleri",
        location="Kahramanmaraş",
        frame_label="00:11 · arama kurtarma ekibi",
    ),
    CorpusEntry(
        corpus_id="KRP-2021-0801-233",
        fingerprint="orman-yangini-manavgat-2021",
        first_published="01.08.2021",
        source="Ulusal haber ajansı arşivi",
        event="2021 Akdeniz orman yangınları",
        location="Antalya / Manavgat",
        frame_label="00:02 · alev hattı",
    ),
    CorpusEntry(
        corpus_id="KRP-2021-0811-091",
        fingerprint="sel-bozkurt-2021",
        first_published="11.08.2021",
        source="Yerel yayın arşivi",
        event="2021 Batı Karadeniz sel felaketi",
        location="Kastamonu / Bozkurt",
        frame_label="00:07 · su altında kalan cadde",
    ),
    CorpusEntry(
        corpus_id="KRP-2020-1030-158",
        fingerprint="deprem-izmir-bayrakli-2020",
        first_published="30.10.2020",
        source="Ulusal haber ajansı arşivi",
        event="2020 İzmir Seferihisar depremi",
        location="İzmir / Bayraklı",
        frame_label="00:03 · çöken bina",
    ),
    CorpusEntry(
        corpus_id="KRP-2022-0219-042",
        fingerprint="baraj-tasma-arsiv-2022",
        first_published="19.02.2022",
        source="Kurumsal basın arşivi",
        event="2022 baraj kapak açılışı tatbikatı",
        location="Adana",
        frame_label="00:09 · savak boşaltımı",
    ),
]

#: Sorgu için hazır indeks — gerçek sistemde FAISS IVF-PQ.
INDEX: dict[int, CorpusEntry] = {entry.phash: entry for entry in ENTRIES}
