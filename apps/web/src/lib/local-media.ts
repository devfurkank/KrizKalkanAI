/**
 * Yüklenen görsel ve videoların tarayıcı içi kopyaları.
 *
 * Sunucu ham medyayı analiz sonrası saklamaz (docs/etik-protokol.md · KVKK).
 * Paylaşılan görseli yalnızca yükleyen tarayıcı, kendi belleğindeki kopyadan
 * gösterir; sayfa yenilenince kopya kaybolur ve bu bilinçlidir.
 */

const uploads = new Map<string, string>();

/** Yayımlanan gönderinin medyasını (blob URL) akışta göstermek için saklar. */
export function rememberUpload(postId: string, objectUrl: string): void {
  uploads.set(postId, objectUrl);
}

export function uploadFor(postId: string): string | undefined {
  return uploads.get(postId);
}
