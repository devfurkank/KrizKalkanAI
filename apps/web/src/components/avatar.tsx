/**
 * Avatar yer tutucusu.
 *
 * Orijinal ekran görüntülerindeki profil fotoğrafları üçüncü taraflara ait
 * olduğu için yeniden üretilmez; yerlerine aynı boyutta degrade daireler
 * kullanılır.
 */
export function Avatar({
  gradient,
  size = 40,
  ring = false,
}: {
  gradient: string;
  size?: number;
  ring?: boolean;
}) {
  return (
    <span
      style={{ width: size, height: size }}
      className={`inline-block shrink-0 rounded-full bg-gradient-to-br ${gradient} ${
        ring ? "ring-2 ring-white dark:ring-nsd-surface" : ""
      }`}
    />
  );
}
