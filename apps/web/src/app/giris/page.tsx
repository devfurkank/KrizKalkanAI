import type { Metadata } from "next";

import { LoginCard } from "@/components/login-card";
import { Logo } from "@/components/logo";

export const metadata: Metadata = {
  title: "Hesabına Giriş Yap · NSosyal",
};

/**
 * Ölçüler orijinal ekran görüntüsünden alınmıştır: ortalanmış ~1520px'lik
 * kapsayıcı, 50/50 bölünme, kart yüksekliği içerik alanının ~%91'i.
 */
export default function GirisPage() {
  return (
    <div className="flex min-h-dvh flex-col bg-black">
      <main className="mx-auto grid w-full max-w-[1520px] flex-1 grid-cols-1 gap-10 px-6 py-7 lg:grid-cols-2 lg:gap-0">
        <div className="flex flex-col items-center justify-center gap-6 text-center">
          <Logo tone="light" />
          <p className="max-w-[600px] text-[18px] leading-[1.45] text-white">
            NSosyal ile gündemi keşfet, düşüncelerinizi paylaşın ve dünyaya bağlanın!
          </p>
        </div>

        <div className="flex justify-center">
          <LoginCard />
        </div>
      </main>

      <div className="mx-auto w-full max-w-[1520px] px-6">
        <footer className="pb-5 text-center text-[12.5px] text-[#6B6B6B] lg:w-1/2">
          Tüm hakları saklıdır. ©2026
        </footer>
      </div>
    </div>
  );
}
