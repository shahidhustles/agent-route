import { useId } from "react";
import type { SVGProps } from "react";

export const MicrosoftWord = (props: SVGProps<SVGSVGElement>) => {
  const safeId = useId().replaceAll(":", "");
  const g = (key: string) => `microsoft_word_${safeId}_${key}`;

  return (
    <svg {...props} viewBox="0 0 486 500">
      <title>Microsoft Word</title>
      <defs>
        <radialGradient
          cx="-689.34"
          cy="753.93"
          fx="-689.34"
          fy="753.93"
          gradientTransform="matrix(47.56 0 0 -20.15 33260.63 15691.18)"
          gradientUnits="userSpaceOnUse"
          id={g("a")}
          r="13.89"
        >
          <stop offset=".18" stopColor="#1657f4" />
          <stop offset=".57" stopColor="#0036c4" />
        </radialGradient>
        <radialGradient
          cx="-730.97"
          cy="806.4"
          fx="-730.97"
          fy="806.4"
          gradientTransform="matrix(-20.22495 21.28288 52.40647 49.82267 -56559.12 -24498.36)"
          gradientUnits="userSpaceOnUse"
          id={g("c")}
          r="13.89"
        >
          <stop offset=".14" stopColor="#d471ff" />
          <stop offset=".83" stopColor="#509df5" stopOpacity="0" />
        </radialGradient>
        <radialGradient
          cx="-682.21"
          cy="801.86"
          fx="-682.21"
          fy="801.86"
          gradientTransform="matrix(0 18.62 101.62 0 -81063.08 13022.32)"
          gradientUnits="userSpaceOnUse"
          id={g("d")}
          r="13.89"
        >
          <stop offset=".28" stopColor="#4f006f" stopOpacity="0" />
          <stop offset="1" stopColor="#4f006f" />
        </radialGradient>
        <radialGradient
          cx="-749.58"
          cy="798.74"
          fx="-749.58"
          fy="798.74"
          gradientTransform="matrix(-28.7167 6.70901 16.06567 68.78884 -33867.69 -49911.37)"
          gradientUnits="userSpaceOnUse"
          id={g("f")}
          r="13.89"
        >
          <stop offset=".06" stopColor="#e4a7fe" />
          <stop offset=".54" stopColor="#e4a7fe" stopOpacity="0" />
        </radialGradient>
        <radialGradient
          cx="-675.64"
          cy="797.48"
          fx="-675.64"
          fy="797.48"
          gradientTransform="matrix(15.99196 15.99755 15.99476 -15.99476 -1949 23805.98)"
          gradientUnits="userSpaceOnUse"
          id={g("g")}
          r="13.89"
        >
          <stop offset=".08" stopColor="#367af2" />
          <stop offset=".87" stopColor="#001a8f" />
        </radialGradient>
        <radialGradient
          cx="-657.62"
          cy="854.65"
          fx="-657.62"
          fy="854.65"
          gradientTransform="matrix(0 11.2 12.76 0 -10796.09 7734.8)"
          gradientUnits="userSpaceOnUse"
          id={g("h")}
          r="13.89"
        >
          <stop offset=".59" stopColor="#2763e5" stopOpacity="0" />
          <stop offset=".97" stopColor="#58aafe" />
        </radialGradient>
        <linearGradient
          gradientTransform="matrix(1 0 0 -1 0 502)"
          gradientUnits="userSpaceOnUse"
          id={g("b")}
          x1="69.43"
          x2="388.45"
          y1="238.11"
          y2="238.11"
        >
          <stop offset="0" stopColor="#66c0ff" />
          <stop offset=".26" stopColor="#0094f0" />
        </linearGradient>
        <linearGradient
          gradientTransform="matrix(1 0 0 -1 0 502)"
          gradientUnits="userSpaceOnUse"
          id={g("e")}
          x1="69.48"
          x2="485.94"
          y1="380.04"
          y2="373.16"
        >
          <stop offset="0" stopColor="#9deaff" />
          <stop offset=".2" stopColor="#3bd5ff" />
        </linearGradient>
      </defs>
      <path
        d="m69.43 376.25 194.4-237.36L486 293.13v158.26c0 26.85-21.76 48.61-48.6 48.61H152.74c-46.01 0-83.31-37.31-83.31-83.33v-40.42Z"
        style={{ fill: `url(#${g("a")})` }}
      />
      <path
        d="M69.43 208.87c0-34.52 27.98-62.5 62.49-62.5h283.11L486 111.11v173.61c0 26.85-21.76 48.61-48.6 48.61H152.74c-46.01 0-83.31 37.31-83.31 83.33v-207.8Z"
        style={{ fill: `url(#${g("b")})` }}
      />
      <path
        d="M69.43 208.87c0-34.52 27.98-62.5 62.49-62.5h283.11L486 111.11v173.61c0 26.85-21.76 48.61-48.6 48.61H152.74c-46.01 0-83.31 37.31-83.31 83.33v-207.8Z"
        style={{ fill: `url(#${g("c")})`, fillOpacity: ".6" }}
      />
      <path
        d="M69.43 208.87c0-34.52 27.98-62.5 62.49-62.5h283.11L486 111.11v173.61c0 26.85-21.76 48.61-48.6 48.61H152.74c-46.01 0-83.31 37.31-83.31 83.33v-207.8Z"
        style={{ fill: `url(#${g("d")})`, fillOpacity: ".1" }}
      />
      <path
        d="M69.43 83.33C69.43 37.31 106.73 0 152.74 0H437.4C464.24 0 486 21.76 486 48.61v69.44c0 26.85-21.76 48.61-48.6 48.61H152.74c-46.01 0-83.31 37.31-83.31 83.33V83.33Z"
        style={{ fill: `url(#${g("e")})` }}
      />
      <path
        d="M69.43 83.33C69.43 37.31 106.73 0 152.74 0H437.4C464.24 0 486 21.76 486 48.61v69.44c0 26.85-21.76 48.61-48.6 48.61H152.74c-46.01 0-83.31 37.31-83.31 83.33V83.33Z"
        style={{ fill: `url(#${g("f")})`, fillOpacity: ".8" }}
      />
      <rect
        height="222.22"
        rx="45.13"
        ry="45.13"
        style={{ fill: `url(#${g("g")})` }}
        width="222.17"
        y="236.11"
      />
      <rect
        height="222.22"
        rx="45.13"
        ry="45.13"
        style={{ fill: `url(#${g("h")})`, fillOpacity: ".65" }}
        width="222.17"
        y="236.11"
      />
      <path
        d="M187.26 283.73 159.92 410.7l-32.69.02-16.14-76.19-16.9 76.19h-33L34.91 283.75h26.95l16.21 83.79 16.11-83.79h33.04l16.87 83.79 15.82-83.79 27.34-.02Z"
        style={{ fill: "#fff" }}
      />
    </svg>
  );
};
