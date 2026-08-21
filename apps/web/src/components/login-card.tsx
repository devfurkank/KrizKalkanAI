"use client";

import { useState } from "react";

import { EyeOffIcon } from "@/components/icons";

export function LoginCard() {
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);

  const canSubmit = identifier.trim().length > 0 && password.length > 0;

  return (
    <div className="flex w-full max-w-[672px] items-center justify-center self-stretch rounded-[26px] bg-white px-6 py-14">
      <form
        className="w-full max-w-[352px]"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        <h1 className="text-center text-[25px] leading-tight font-bold text-ns-body">
          Hesabına Giriş Yap
        </h1>
        <p className="mt-1.5 text-center text-[14px] text-[#4D5562]">
          Devam etmek için bilgilerini gir.
        </p>

        <div className="mt-7 flex flex-col gap-2.5">
          <input
            type="text"
            autoComplete="username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="Kullanıcı adı veya e-posta"
            aria-label="Kullanıcı adı veya e-posta"
            className="h-[46px] w-full rounded-full border border-[#4E80EE] bg-white px-4 text-[14.5px] text-ns-ink outline-none ring-[3px] ring-[#5EA7F8]/25 placeholder:text-ns-subtle"
          />

          <div className="relative">
            <input
              type={visible ? "text" : "password"}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Şifre"
              aria-label="Şifre"
              className="h-[46px] w-full rounded-full border border-transparent bg-[#F4F4F6] pr-12 pl-4 text-[14.5px] text-ns-ink outline-none placeholder:text-ns-subtle focus:border-[#4E80EE] focus:bg-white"
            />
            <button
              type="button"
              onClick={() => setVisible((v) => !v)}
              aria-label={visible ? "Şifreyi gizle" : "Şifreyi göster"}
              className="absolute top-1/2 right-4 -translate-y-1/2 text-ns-muted transition-colors hover:text-ns-body"
            >
              <EyeOffIcon className="size-[19px]" />
            </button>
          </div>
        </div>

        <div className="mt-3 text-center">
          <a href="#" className="text-[13px] text-[#4D5562] hover:underline">
            Şifrenizi mi unuttunuz?
          </a>
        </div>

        <button
          type="submit"
          disabled={!canSubmit}
          className={`mt-4 h-[46px] w-full rounded-full text-[15px] font-medium transition-all ${
            canSubmit
              ? "bg-gradient-to-r from-ns-grad-from to-ns-grad-to text-white hover:opacity-92"
              : "cursor-default bg-[#ECECEF] text-[#80848F]"
          }`}
        >
          Hesabına Giriş Yap
        </button>

        <p className="mt-5 text-center text-[13.5px] text-ns-body">
          Hesabınız yok mu?{" "}
          <a href="#" className="font-semibold text-ns-link hover:underline">
            Hesap Oluştur
          </a>
        </p>
        <p className="mt-4 text-center text-[13.5px] text-ns-body">
          Hesabına ulaşamıyor musun?{" "}
          <a href="#" className="font-semibold text-ns-link hover:underline">
            Bizimle iletişime geç
          </a>
        </p>
      </form>
    </div>
  );
}
