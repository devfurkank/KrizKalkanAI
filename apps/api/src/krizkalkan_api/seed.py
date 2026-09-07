"""Demo akışını dolduran tohum verisi.

Rapor 5.1'deki dört senaryo burada birebir karşılanır; sunumda gösterilecek
akış budur. Her gönderi gerçek analiz boru hattından geçirilir — sonuçlar
sabit kodlanmaz.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from krizkalkan_core.pipeline import pipeline
from krizkalkan_core.schemas import Author, MediaRef, Post

from krizkalkan_api.store import store

AUTHORS = {
    "afad": Author(
        name="AFAD",
        handle="afadbaskanlik",
        verified=True,
        avatar="from-red-500 via-rose-600 to-slate-800",
    ),
    "dmm": Author(
        name="Dezenformasyonla Mücadele Merkezi",
        handle="dmm",
        verified=True,
        avatar="from-slate-200 to-slate-400",
    ),
    "haber": Author(
        name="Bölge Haber",
        handle="bolgehaber",
        verified=False,
        avatar="from-amber-200 to-orange-400",
    ),
    "kullanici1": Author(
        name="Mehmet K.",
        handle="mehmetk",
        verified=False,
        avatar="from-sky-300 to-blue-500",
    ),
    "kullanici2": Author(
        name="Zeynep A.",
        handle="zeynepa",
        verified=False,
        avatar="from-violet-300 to-purple-500",
    ),
    "kullanici3": Author(
        name="Emre T.",
        handle="emret",
        verified=False,
        avatar="from-emerald-300 to-teal-500",
    ),
    "kullanici4": Author(
        name="Ayşe D.",
        handle="aysed",
        verified=False,
        avatar="from-pink-300 to-rose-500",
    ),
}

#: (yazar, metin, medya türü, parmak izi, dakika önce, yayılım/dk)
SEED_POSTS: list[tuple[str, str, str, str | None, int, float]] = [
    # ── Senaryo 1: eski görüntünün yeni afet olarak paylaşılması ──
    (
        "haber",
        "Şanlıurfa'da az önce çekildi! Bina tamamen yıkıldı, durum çok vahim. "
        "Hemen paylaşın, herkes bilsin!",
        "video",
        "deprem-yikim-hatay-2023",
        7,
        22.0,
    ),
    # ── Senaryo 2: kurum taklidiyle panik yayılması ──
    (
        "kullanici1",
        "AFAD açıkladı: ikinci büyük deprem bekleniyor. Kesin bilgi, "
        "önümüzdeki 6 saat içinde olacak. Herkes bilsin!",
        "yok",
        None,
        12,
        18.0,
    ),
    # ── Senaryo 3: yardım çağrısı — Kural 0 korumalı ──
    (
        "kullanici2",
        "ACİL! Kardeşim enkaz altında, hâlâ ses geliyor. "
        "Adres: Bahçelievler Mah. 12. Sokak No:4. Yardım edin, ekip gönderin lütfen!",
        "yok",
        None,
        4,
        140.0,
    ),
    # ── Senaryo 4: sentetik medya, yüksek güven → sürtünme ekranı ──
    (
        "kullanici3",
        "Vali konuşma yaptı, şehir tahliye ediliyor. Herkes güvenli bölgeye gitsin.",
        "video",
        "ai-klon-yetkili-ses",
        18,
        26.0,
    ),
    # ── Resmî, doğrulanan içerik ──
    (
        "afad",
        "Bölgede arama kurtarma çalışmaları sürüyor. 42 ekip sahada görev yapıyor. "
        "Resmî açıklamalarımızı bu hesaptan takip ediniz.",
        "yok",
        None,
        22,
        18.0,
    ),
    # ── DMM tekzibi ──
    (
        "dmm",
        "Baraj yıkıldı iddiası gerçeği yansıtmamaktadır. DSİ ve Valilik, "
        "barajlarda yapısal hasar bulunmadığını bildirmiştir.",
        "yok",
        None,
        25,
        9.0,
    ),
    # ── Aynı iddianın ikinci varyantı (Kriz Radar kümelemesi için) ──
    (
        "kullanici4",
        "Duyduğuma göre baraj yıkıldı, şehri terk edin! Medya bunu gizliyor.",
        "yok",
        None,
        9,
        95.0,
    ),
    # ── Provokatif çerçeveleme ──
    (
        "kullanici1",
        "Sorumlular hesap versin, hepimiz sokağa dökülelim! Gerçekleri saklıyorlar, "
        "kimse konuşmuyor.",
        "yok",
        None,
        15,
        33.0,
    ),
    # ── Yetersiz kanıt: dağılım dışı medya ──
    (
        "kullanici3",
        "Bir şeyler oluyor galiba, net göremedim.",
        "video",
        "dusuk-cozunurluk-kisa-klip",
        30,
        4.0,
    ),
    # ── Temiz içerik ──
    (
        "kullanici4",
        "Meteoroloji bölge için sarı kodlu kuvvetli yağış uyarısı yayımladı. Dikkatli olalım.",
        "yok",
        None,
        28,
        6.0,
    ),
]

MEDIA_BY_KIND: dict[str, MediaRef] = {
    "video": MediaRef(
        kind="video",
        poster="from-slate-500 via-slate-600 to-slate-800",
        label="Video · 00:24",
    ),
    "grid": MediaRef(
        kind="grid",
        tiles=[
            "from-sky-200 via-blue-300 to-indigo-400",
            "from-slate-300 via-sky-400 to-blue-600",
            "from-rose-200 via-orange-200 to-amber-300",
            "from-cyan-200 via-sky-300 to-blue-400",
        ],
    ),
}


def seed() -> None:
    """Depoyu demo verisiyle doldurur. Tekrar çağrılırsa önce temizler."""
    store.clear()
    pipeline.clear_cache()
    now = datetime.now(UTC)

    for author_key, body, media_kind, fingerprint, minutes_ago, spread in SEED_POSTS:
        post_id = f"g_{uuid.uuid4().hex[:10]}"
        analysis = pipeline.analyse(
            body=body,
            media_kind=media_kind,
            media_fingerprint=fingerprint,
            content_id=post_id,
            spread_per_minute=spread,
        )
        created = now - timedelta(minutes=minutes_ago)
        post = Post(
            id=post_id,
            author=AUTHORS[author_key],
            body=body,
            created_at=created,
            media=MEDIA_BY_KIND.get(media_kind),
            stats={
                "replies": int(spread // 9),
                "quotes": int(spread // 24),
                "boosts": int(spread * 2.4),
                "views": int(spread * 41),
            },
            analysis=analysis,
        )
        store.add_post(post, spread_per_minute=spread)

        if analysis.intervention.protected_by_rule_zero:
            store.log(
                "koruma_kuralı_uygulandı",
                post_id=post_id,
                detail="Kural 0 · yardım çağrısı korundu, hiçbir müdahale uygulanmadı",
            )
        elif analysis.intervention.level.value != "SEVIYE_0":
            store.log(
                f"müdahale_{analysis.intervention.level.value.lower()}",
                post_id=post_id,
                detail=f"{analysis.verdict} · {analysis.intervention.label}",
            )

    store.log(
        "tohum_verisi_yüklendi",
        detail=f"{len(SEED_POSTS)} gönderi analiz edildi, 0 içerik kaldırıldı",
    )
