/**
 * Arayüz klonunun demo verisi.
 *
 * Not: Orijinal ekran görüntülerindeki fotoğraflar üçüncü taraflara ait olduğu
 * için medya alanları yeniden üretilmez; yerlerine aynı en-boy oranında
 * degrade yer tutucular kullanılır.
 */

export type Audience = "herkes" | "takipciler" | "belirli";

export interface Author {
  name: string;
  handle: string;
  verified: boolean;
  /** Avatar yer tutucusu için degrade sınıfı. */
  avatar: string;
}

export interface Post {
  id: string;
  author: Author;
  time: string;
  body: string;
  /** Gövde içindeki hashtag'ler otomatik renklendirilir. */
  media?: { kind: "grid"; tiles: string[] } | { kind: "video"; poster: string };
  stats: { replies: number; quotes: number; boosts: number; views: number };
}

export const currentUser: Author = {
  name: "Furkan Keskin",
  handle: "furkankeskin",
  verified: false,
  avatar: "from-slate-400 to-slate-600",
};

export const stories = [
  { id: "1", label: "teknofest", avatar: "from-rose-500 via-red-600 to-indigo-800" },
  { id: "2", label: "selcukbayra...", avatar: "from-sky-600 to-slate-800" },
  { id: "3", label: "baykartech", avatar: "from-slate-100 to-slate-300" },
];

export const trends = [
  { tag: "TeknofestMaviVatan", count: "1,2B gönderi" },
  { tag: "Fatih", count: "121 gönderi" },
  { tag: "TEKNOFEST", count: "978 gönderi" },
  { tag: "Pakistan", count: "99 gönderi" },
  { tag: "Somali", count: "47 gönderi" },
];

export const posts: Post[] = [
  {
    id: "p1",
    author: {
      name: "T3 Vakfı",
      handle: "turkiyeteknolojitakimi",
      verified: true,
      avatar: "from-amber-100 to-rose-200",
    },
    time: "37dk",
    body: "#TeknofestMaviVatan seyir defterine bir gün daha eklendi! 📝 🌊",
    media: {
      kind: "grid",
      tiles: [
        "from-sky-200 via-blue-300 to-indigo-400",
        "from-slate-300 via-sky-400 to-blue-600",
        "from-rose-200 via-orange-200 to-amber-300",
        "from-cyan-200 via-sky-300 to-blue-400",
      ],
    },
    stats: { replies: 1, quotes: 0, boosts: 20, views: 217 },
  },
  {
    id: "p2",
    author: {
      name: "TEKNOFEST",
      handle: "teknofest",
      verified: true,
      avatar: "from-rose-500 via-red-600 to-indigo-800",
    },
    time: "42dk",
    body: "Nerede olursak olalım, biz buyuz! 😎\n\n⚓ #TeknofestMaviVatan 🚀",
    media: { kind: "video", poster: "from-sky-300 via-cyan-200 to-slate-400" },
    stats: { replies: 4, quotes: 1, boosts: 63, views: 1204 },
  },
  {
    id: "p3",
    author: {
      name: "Baykar",
      handle: "baykartech",
      verified: true,
      avatar: "from-slate-100 to-slate-300",
    },
    time: "1sa",
    body: "Mavi Vatan'da göreve hazırız. #TEKNOFEST #MaviVatan",
    stats: { replies: 12, quotes: 3, boosts: 240, views: 8931 },
  },
];

export const audienceOptions: {
  value: Audience;
  label: string;
  description: string;
}[] = [
  { value: "herkes", label: "Herkese açık", description: "Herkes bu gönderiyi görebilir" },
  {
    value: "takipciler",
    label: "Takipçiler",
    description: "Sadece takipçileriniz bu gönderiyi görebilir",
  },
  { value: "belirli", label: "Belirli kişiler", description: "Gönderide değinilen herkes" },
];
