import Image from "next/image";

import relayLogo from "@/public/brand/relay-logo.png";

export function RelayLogo({ size = 28 }: { size?: number }) {
  return (
    <Image
      src={relayLogo}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      className="shrink-0"
    />
  );
}
