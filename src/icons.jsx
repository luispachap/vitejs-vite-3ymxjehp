// ============================================================
//  AgroGestión — Iconografía propia (SVG embebido)
//
//  ¿Por qué SVG y no una fuente de iconos?
//  Los iconos viven DENTRO del código de la app: funcionan
//  siempre, aunque no haya internet. Nada que descargar.
//
//  Uso:  <Ic e="🌾" />        ← traduce un emoji guardado en datos
//        <Ic name="wheat" />  ← o pide el icono por nombre
//  El tamaño lo hereda del font-size del contenedor (1em)
//  y el color de currentColor, igual que un carácter de texto.
// ============================================================
import React, { useState, useEffect } from "react";

/* Cada icono son trazos sobre una retícula de 24×24. */
export const ICONS = {
  // ── Navegación / módulos ──
  dashboard: <><rect x="3.5" y="3.5" width="7" height="9" rx="2" /><rect x="13.5" y="3.5" width="7" height="5.5" rx="2" /><rect x="13.5" y="12.5" width="7" height="8" rx="2" /><rect x="3.5" y="16" width="7" height="4.5" rx="2" /></>,
  receipts: <><path d="M6 3.5h12v17l-2.4-1.6-2.4 1.6-2.4-1.6-2.4 1.6-2.4-1.6z" /><path d="M9.5 8h5M9.5 11.5h5M9.5 15h2.5" /></>,
  chartUp: <><path d="M3.5 4v16.5H20" /><path d="M7 15l3.5-4 3 2.5 4.5-6" /><path d="M18 7.5V11M18 7.5h-3.5" /></>,
  chartDown: <><path d="M3.5 4v16.5H20" /><path d="M7 9l3.5 4 3-2.5 4.5 6" /><path d="M18 16.5V13M18 16.5h-3.5" /></>,
  cash: <><rect x="2.5" y="6" width="19" height="12" rx="2.5" /><circle cx="12" cy="12" r="2.6" /><path d="M6 9.5v.01M18 14.5v.01" /></>,
  box: <><path d="M3.5 8L12 3.5 20.5 8v8L12 20.5 3.5 16z" /><path d="M3.5 8L12 12.5 20.5 8M12 12.5v8" /></>,
  toolbox: <><rect x="3" y="8.5" width="18" height="11" rx="2.5" /><path d="M8.5 8.5V6.8A1.8 1.8 0 0 1 10.3 5h3.4a1.8 1.8 0 0 1 1.8 1.8v1.7M3 13h18M10 13v2.5M14 13v2.5" /></>,
  checkCircle: <><circle cx="12" cy="12" r="8.5" /><path d="M8.4 12.3l2.5 2.5 4.7-5.2" /></>,
  clipboardCheck: <><rect x="5" y="4.5" width="14" height="16.5" rx="2.5" /><path d="M9 4.5V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v.5" /><path d="M8.8 13.5l2.3 2.3 4.2-4.7" /></>,
  clipboard: <><rect x="5" y="4.5" width="14" height="16.5" rx="2.5" /><path d="M9 4.5V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v.5" /><path d="M9 11h6M9 15h6" /></>,
  pencilSquare: <><rect x="3.5" y="5" width="15.5" height="15.5" rx="3" /><path d="M20.5 3.5l-8.3 8.3-.9 3 3-.9 8.2-8.2a1.6 1.6 0 0 0-2-2.2z" transform="translate(-2 0) scale(.92)" /></>,
  editNote: <><path d="M4 6h10M4 10h6M4 14h5" /><path d="M19.7 8.3a1.9 1.9 0 0 0-2.7-2.7L10 12.6 9 16.5l3.9-1z" /></>,
  calendar: <><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 9.5h17M8 3v3.5M16 3v3.5" /><path d="M7.5 13.5h3M13.5 13.5h3M7.5 17h3" /></>,
  calendarAlt: <><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 9.5h17M8 3v3.5M16 3v3.5" /><circle cx="12" cy="14.8" r="2.2" /></>,
  users: <><circle cx="9" cy="8.5" r="3.2" /><path d="M3.5 19.5c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" /><circle cx="16.8" cy="9.5" r="2.5" /><path d="M17.5 14.6c1.9.5 3 2 3.4 4.4" /></>,
  user: <><circle cx="12" cy="8" r="3.6" /><path d="M5 20c.8-3.8 3.5-5.8 7-5.8s6.2 2 7 5.8" /></>,
  farmer: <><circle cx="12" cy="10" r="3.2" /><path d="M5.5 20.5c.7-3.4 3.1-5.2 6.5-5.2s5.8 1.8 6.5 5.2" /><path d="M7.5 8.2c0-2.6 2-4.7 4.5-4.7s4.5 2.1 4.5 4.7M5 8.2h14" /></>,
  hardhat: <><path d="M4.5 15a7.5 7.5 0 0 1 15 0" /><path d="M3 17.5c0-1.4 1.1-2.5 2.5-2.5h13c1.4 0 2.5 1.1 2.5 2.5v.5H3z" /><path d="M12 4.5v4" /></>,
  map: <><path d="M3.5 6.5l5-2.5 7 2.5 5-2.5v13.5l-5 2.5-7-2.5-5 2.5z" /><path d="M8.5 4v13.5M15.5 6.5V20" /></>,
  news: <><rect x="3.5" y="4.5" width="17" height="15" rx="2.5" /><path d="M7.5 9h9M7.5 12.5h9M7.5 16h5" /></>,
  save: <><path d="M4.5 6.5a2 2 0 0 1 2-2H16l3.5 3.5v10.5a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2z" /><path d="M8 4.5V9h7V4.5" /><rect x="8" y="14" width="8" height="5.5" rx="1" /></>,
  lock: <><rect x="5" y="10.5" width="14" height="10" rx="2.5" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" /><path d="M12 14.5v2.5" /></>,
  cloudUp: <><path d="M7 18.5a4.5 4.5 0 0 1-.6-8.95 6 6 0 0 1 11.6 1.6A3.9 3.9 0 0 1 17.5 18.5z" /><path d="M12 20.5v-6M9.5 16.5l2.5-2.5 2.5 2.5" /></>,
  target: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.8" /><circle cx="12" cy="12" r="1.2" /></>,
  bellAlert: <><path d="M6 15.5V11a6 6 0 0 1 12 0v4.5l1.8 2.5H4.2z" /><path d="M10 20.5a2.2 2.2 0 0 0 4 0" /></>,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 7.8v.01" /></>,
  bot: <><rect x="4.5" y="8" width="15" height="11" rx="3" /><path d="M12 8V4.5M12 4.5h.01" /><circle cx="9" cy="13" r="1" /><circle cx="15" cy="13" r="1" /><path d="M9.5 16.3h5" /></>,
  droplet: <><path d="M12 3.5s6 6.2 6 10.5a6 6 0 0 1-12 0C6 9.7 12 3.5 12 3.5z" /><path d="M9.5 14a2.6 2.6 0 0 0 2 2.4" /></>,
  trash: <><path d="M4.5 6.5h15M9.5 6.5V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v1.5" /><path d="M6.5 6.5l1 13a1.5 1.5 0 0 0 1.5 1h6a1.5 1.5 0 0 0 1.5-1l1-13" /><path d="M10 10.5v6M14 10.5v6" /></>,
  pinPoint: <><path d="M12 21s-6.5-6-6.5-10.7a6.5 6.5 0 0 1 13 0C18.5 15 12 21 12 21z" /><circle cx="12" cy="10.3" r="2.3" /></>,
  tractor: <><circle cx="7.5" cy="16" r="4" /><circle cx="7.5" cy="16" r="1.2" /><circle cx="18" cy="17.5" r="2.6" /><path d="M11.4 17.5h4M5 12V6.5h6l2 5.5" /><path d="M13 12h4.5a2 2 0 0 1 2 2v1.5M11 6.5h4l1.5 5" /></>,
  bulb: <><path d="M8.5 14.5a5.8 5.8 0 1 1 7 0c-.9.7-1.3 1.4-1.4 2.5h-4.2c-.1-1.1-.5-1.8-1.4-2.5z" /><path d="M9.9 20h4.2M11 22h2" /></>,
  spray: <><path d="M8 9.5h6l-1 11H9z" /><path d="M10 9.5V7h2v2.5" /><path d="M11 4.5h.01M14.5 4.5h.01M16.5 6.5h.01M16.5 3h.01" /><path d="M9.3 13h5.4" /></>,
  truck: <><path d="M2.5 6.5h11v10h-11z" /><path d="M13.5 10h4l3 3.5v3h-7" /><circle cx="6.5" cy="17.5" r="2" /><circle cx="17" cy="17.5" r="2" /></>,
  tag: <><path d="M3.5 11.5v-8h8l9 9-8 8z" /><circle cx="8" cy="8" r="1.4" /></>,
  phoneOff: <><rect x="7" y="3" width="10" height="18" rx="2.5" /><path d="M11 17.8h2" /><path d="M4 4l16 16" /></>,
  camera: <><path d="M3.5 8.5A2 2 0 0 1 5.5 6.5H8l1.5-2h5l1.5 2h2.5a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" /><circle cx="12" cy="13" r="3.4" /></>,
  fuel: <><path d="M5 20.5V5.5a2 2 0 0 1 2-2h5a2 2 0 0 1 2 2v15" /><path d="M3.5 20.5h12" /><path d="M6.8 6.8h5.4v4H6.8z" /><path d="M14 11h2.2a1.8 1.8 0 0 1 1.8 1.8v3.4a1.4 1.4 0 1 0 2.8 0V9.5L18 6.7" /></>,
  bolt: <><path d="M13.5 3L5.5 13.5h5L10.5 21l8-10.5h-5z" /></>,
  dna: <><path d="M7 3.5c0 6 10 5 10 11M17 3.5c0 2.5-1.7 4-4 5M7 20.5c0-2.5 1.7-4 4-5M17 20.5c0-6-10-5-10-11" /><path d="M8.2 6.5h7.6M8.2 17.5h7.6" /></>,
  printer: <><path d="M7 8V3.5h10V8" /><rect x="3.5" y="8" width="17" height="8.5" rx="2" /><path d="M7 13.5h10v7H7z" /><path d="M17.5 11h.01" /></>,
  moneyBag: <><path d="M9.5 7L7.8 4.2c-.4-.7.1-1.7 1-1.7h6.4c.9 0 1.4 1 1 1.7L14.5 7" /><path d="M9.5 7h5c3.2 2.2 5 5.3 5 8.5 0 3.4-2.6 6-6 6h-3c-3.4 0-6-2.6-6-6 0-3.2 1.8-6.3 5-8.5z" /><path d="M12 10.5v7M14 12h-3a1.5 1.5 0 0 0 0 3h2a1.5 1.5 0 0 1 0 3h-3" /></>,
  xCircle: <><circle cx="12" cy="12" r="8.5" /><path d="M9 9l6 6M15 9l-6 6" /></>,
  chat: <><path d="M4 6a2.5 2.5 0 0 1 2.5-2.5h11A2.5 2.5 0 0 1 20 6v8a2.5 2.5 0 0 1-2.5 2.5H9L4 20.5z" /><path d="M8.5 8.5h7M8.5 12h4.5" /></>,
  trayDown: <><path d="M3.5 14v4a2.5 2.5 0 0 0 2.5 2.5h12a2.5 2.5 0 0 0 2.5-2.5v-4" /><path d="M12 3.5V14M8 10.5l4 4 4-4" /></>,
  trayUp: <><path d="M3.5 14v4a2.5 2.5 0 0 0 2.5 2.5h12a2.5 2.5 0 0 0 2.5-2.5v-4" /><path d="M12 14V3.5M8 7l4-4 4 4" /></>,
  wrench: <><path d="M14.5 6.5a4.5 4.5 0 0 1 5.6-4.4l-3.4 3.4 2.8 2.8 3.4-3.4a4.5 4.5 0 0 1-5.9 5.4L9 18.3A2.1 2.1 0 1 1 6 15.4l8.5-8.9z" transform="scale(.92) translate(1 1)" /></>,
  sparkles: <><path d="M12 4l1.8 4.7L18.5 10.5l-4.7 1.8L12 17l-1.8-4.7L5.5 10.5l4.7-1.8z" /><path d="M18.5 15.5l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z" /></>,
  linkIcon: <><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.2 1.2" /><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.2-1.2" /></>,
  drone: <><circle cx="5.5" cy="5.5" r="2.5" /><circle cx="18.5" cy="5.5" r="2.5" /><path d="M7.3 7.3l2.7 2.7M16.7 7.3L14 10M7 18l3-3.5M17 18l-3-3.5" /><rect x="9.5" y="10" width="5" height="5" rx="1.5" /><path d="M5 18.5h4M15 18.5h4" /></>,
  refresh: <><path d="M4.5 12a7.5 7.5 0 0 1 13-5.2M19.5 12a7.5 7.5 0 0 1-13 5.2" /><path d="M17.5 3v4h-4M6.5 21v-4h4" /></>,
  microscope: <><path d="M9 3.5h4v7a3.5 3.5 0 0 1-4-.5z" transform="rotate(20 11 7)" /><path d="M6 20.5h13M9 17.5h7" /><path d="M16 14.5a6 6 0 0 0-4.5-9.8" /><path d="M8 14.5h4" /></>,
  hourglass: <><path d="M6.5 3.5h11M6.5 20.5h11M8 3.5v3.5L12 12 8 17v3.5M16 3.5v3.5L12 12l4 5v3.5" /></>,
  factory: <><path d="M3.5 20.5V9.5l5.5 3v-3l5.5 3V6.5h6v14z" /><path d="M17 10.5v.01M17 14v.01M17 17.5v.01" /></>,
  barn: <><path d="M4 20.5V9.5L12 4l8 5.5v11" /><path d="M9 20.5v-7h6v7" /><path d="M9 13.5l6 4.5M15 13.5l-6 4.5" /><path d="M2.5 20.5h19" /></>,
  star: <><path d="M12 3.8l2.5 5.2 5.7.7-4.2 3.9 1.1 5.6-5.1-2.8-5.1 2.8 1.1-5.6-4.2-3.9 5.7-.7z" /></>,
  briefcase: <><rect x="3.5" y="7.5" width="17" height="12.5" rx="2.5" /><path d="M9 7.5V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.5" /><path d="M3.5 12.5h17M12 11v3" /></>,
  scale: <><path d="M12 4v16.5M7 20.5h10" /><path d="M4 7h16" /><path d="M6.5 7l-2.8 6a3 3 0 0 0 5.6 0zM17.5 7l-2.8 6a3 3 0 0 0 5.6 0z" /></>,
  installMobile: <><rect x="6.5" y="3" width="11" height="18" rx="2.5" /><path d="M12 8v6M9.5 11.5l2.5 2.5 2.5-2.5M10.5 17.8h3" /></>,
  home: <><path d="M4 11.5L12 4l8 7.5" /><path d="M6 10v10.5h12V10" /><path d="M10 20.5v-6h4v6" /></>,
  satellite: <><rect x="9.5" y="9.5" width="5" height="5" rx="1" transform="rotate(45 12 12)" /><path d="M6 9.5L9.5 6l2.5 2.5L8.5 12zM15.5 12L12 15.5l2.5 2.5 3.5-3.5z" transform="rotate(0)" /><path d="M17 4.5a4 4 0 0 1 2.5 2.5" /></>,
  cog: <><circle cx="12" cy="12" r="3" /><path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6 6l1.6 1.6M16.4 16.4L18 18M18 6l-1.6 1.6M7.6 16.4L6 18" /></>,
  helmetCross: <><path d="M4.5 14a7.5 7.5 0 0 1 15 0v3.5a1.5 1.5 0 0 1-1.5 1.5H6a1.5 1.5 0 0 1-1.5-1.5z" /><path d="M12 8.5v4M10 10.5h4" /></>,
  arrowDown: <><path d="M12 4.5v15M5.5 13l6.5 6.5L18.5 13" /></>,
  arrowUp: <><path d="M12 19.5v-15M5.5 11L12 4.5 18.5 11" /></>,
  arrowRight: <><path d="M4.5 12h15M13 5.5l6.5 6.5-6.5 6.5" /></>,
  book: <><path d="M4.5 5.5A2.5 2.5 0 0 1 7 3h13v15.5H7A2.5 2.5 0 0 0 4.5 21z" /><path d="M20 18.5v2.5H7a2.5 2.5 0 0 1-2.5-2.5" /><path d="M9 8h7" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  docLines: <><path d="M6 3.5h8.5L19 8v12.5H6z" /><path d="M14 3.5V8.5H19" /><path d="M9 12.5h6M9 16h6" /></>,
  doc: <><path d="M6 3.5h8.5L19 8v12.5H6z" /><path d="M14 3.5V8.5H19" /></>,
  flag: <><path d="M6 21V4" /><path d="M6 5c4-2.3 8 2.3 12 0v8c-4 2.3-8-2.3-12 0" /></>,
  moneyFly: <><rect x="2.5" y="7" width="15" height="10" rx="2" /><circle cx="10" cy="12" r="2.2" /><path d="M20 7l1.5-1.5M20.5 12H22M20 17l1.5 1.5" /></>,
  eye: <><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="3" /></>,
  timer: <><circle cx="12" cy="13.5" r="7.5" /><path d="M12 13.5V9M10 2.5h4M12 2.5V6" /></>,
  alarm: <><circle cx="12" cy="13" r="7.5" /><path d="M12 9.5V13l2.5 2M4.5 5L3 6.5M19.5 5L21 6.5" /></>,
  play: <><path d="M8 5.5l11 6.5-11 6.5z" /></>,
  building: <><rect x="5" y="3.5" width="14" height="17" rx="1.5" /><path d="M9 7.5h2M13 7.5h2M9 11h2M13 11h2M9 14.5h2M13 14.5h2" /><path d="M10.5 20.5v-3h3v3" /></>,
  gift: <><rect x="4" y="8.5" width="16" height="4" rx="1" /><path d="M6 12.5v8h12v-8" /><path d="M12 8.5v12" /><path d="M12 8.5C10 4.5 5.5 5 6.5 8.5zM12 8.5c2-4 6.5-3.5 5.5 0z" /></>,
  undo: <><path d="M8.5 5L4 9.5 8.5 14" /><path d="M4 9.5h10a6 6 0 0 1 0 12h-3" /></>,
  mail: <><rect x="3" y="5.5" width="18" height="13" rx="2.5" /><path d="M4 7.5l8 6 8-6" /></>,
  bus: <><rect x="4.5" y="4" width="15" height="13.5" rx="2.5" /><path d="M4.5 10.5h15" /><path d="M8 21v-2.5M16 21v-2.5" /><path d="M8 14.5h.01M16 14.5h.01" /></>,
  recycle: <><path d="M7 8.5L9.5 4l3 5" /><path d="M9.8 9H4.5l2.2 4" /><path d="M17.2 8L20 12.5l-5.5.2" /><path d="M18 16l-2.5 4.5h-6" /><path d="M8 18l-2.5-4 2.7-4.6" transform="translate(1 2) scale(.8)" /></>,
  bank: <><path d="M3.5 9.5L12 3.5l8.5 6z" /><path d="M5 9.5v8M9.5 9.5v8M14.5 9.5v8M19 9.5v8" /><path d="M3.5 17.5h17M2.5 20.5h19" /></>,
  store: <><path d="M4 9l1.5-5h13L20 9" /><path d="M4 9a2.6 2.6 0 0 0 5.3 0 2.6 2.6 0 0 0 5.4 0A2.6 2.6 0 0 0 20 9" /><path d="M5.5 11.5v9h13v-9" /><path d="M9.5 20.5v-5.5h5v5.5" /></>,
  crane: <><path d="M4 20.5h16M7 20.5V5l10 3.5v12" /><path d="M7 8.5L17 12" /><path d="M17 8.5v-3M17 5.5L7 5" /></>,
  ruler: <><rect x="2.5" y="9" width="19" height="6" rx="1.5" transform="rotate(-25 12 12)" /><path d="M8 13.5l1.2 2.2M11.5 11.6l1.2 2.2M15 9.7l1.2 2.2" transform="rotate(0)" /></>,
  compass: <><circle cx="12" cy="12" r="8.5" /><path d="M15.5 8.5l-2 5-5 2 2-5z" /></>,
  sunCloud: <><circle cx="8" cy="8.5" r="3.5" /><path d="M8 2.5v1.7M2.5 8.5h1.7M4 4.5l1.2 1.2" /><path d="M10 18.5h7.5a3 3 0 0 0 .4-6 4.5 4.5 0 0 0-8.4-1.4A3.8 3.8 0 0 0 10 18.5z" /></>,
  thumbUp: <><path d="M7 11l4-7.5c1.4 0 2.5 1.1 2.5 2.5V9.5h5a2 2 0 0 1 2 2.3l-1 6.5a2 2 0 0 1-2 1.7H7" /><path d="M7 11H3.5v9H7z" /></>,
  checkbox: <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="M8.4 12.2l2.4 2.4 4.8-5.2" /></>,
  shuffle: <><path d="M3.5 6.5h3l10 11h4" /><path d="M20.5 17.5l-2.5 2.5M20.5 17.5L18 15" /><path d="M3.5 17.5h3l3-3.3M13.5 9.4l3-3.4h4" /><path d="M20.5 6.5L18 4M20.5 6.5L18 9" /></>,
  calculator: <><rect x="5" y="3" width="14" height="18" rx="2.5" /><rect x="8" y="6" width="8" height="3.5" rx="1" /><path d="M8.5 13.5h.01M12 13.5h.01M15.5 13.5h.01M8.5 17h.01M12 17h.01M15.5 17h.01" /></>,
  trophy: <><path d="M8 4h8v6a4 4 0 0 1-8 0z" /><path d="M8 5.5H4.5a3.5 3.5 0 0 0 3.6 3.5M16 5.5h3.5a3.5 3.5 0 0 1-3.6 3.5" /><path d="M12 14v3M8.5 20.5h7M10 17h4v3.5h-4z" /></>,
  smartphone: <><rect x="6.5" y="3" width="11" height="18" rx="2.5" /><path d="M10.5 17.8h3" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="M15.5 15.5L21 21" /></>,
  crown: <><path d="M4 8.5l4 3.5 4-6.5 4 6.5 4-3.5-1.5 9.5h-13z" /><path d="M6.5 21h11" /></>,
  shield: <><path d="M12 3.5l7.5 2.7v5.3c0 4.6-3.1 7.7-7.5 9.5-4.4-1.8-7.5-4.9-7.5-9.5V6.2z" /><path d="M8.8 12l2.3 2.3 4.1-4.6" /></>,
  moon: <><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" /></>,
  logout: <><path d="M14 4.5H7A2.5 2.5 0 0 0 4.5 7v10A2.5 2.5 0 0 0 7 19.5h7" /><path d="M10.5 12H21M17.5 8.5L21 12l-3.5 3.5" /></>,
  loop: <><path d="M7 12a5 5 0 1 1 5 5" /><path d="M12 17a5 5 0 1 1 5-5" /></>,
  cart: <><circle cx="9.5" cy="19" r="1.6" /><circle cx="17" cy="19" r="1.6" /><path d="M3 4.5h2.5l2.3 10.5a1.5 1.5 0 0 0 1.5 1.2h7.6a1.5 1.5 0 0 0 1.5-1.2l1.6-7.5H6.6" /></>,

  // ── Campo / cultivo ──
  wheat: <><path d="M12 21V7" /><path d="M12 7C12 4.8 10.5 3 8.5 3c0 2.2 1.5 4 3.5 4zM12 7c0-2.2 1.5-4 3.5-4 0 2.2-1.5 4-3.5 4z" /><path d="M12 12c-.2-2.2-1.8-3.8-4-4 .2 2.2 1.8 3.8 4 4zM12 12c.2-2.2 1.8-3.8 4-4-.2 2.2-1.8 3.8-4 4z" /><path d="M12 17c-.2-2.2-1.8-3.8-4-4 .2 2.2 1.8 3.8 4 4zM12 17c.2-2.2 1.8-3.8 4-4-.2 2.2-1.8 3.8-4 4z" /></>,
  sprout: <><path d="M12 21v-8" /><path d="M12 13c0-3.5-2.7-6.3-6.5-6.5C5.7 10 8.4 13 12 13z" /><path d="M12 10.5c0-3 2.3-5.5 5.8-5.7.2 3.2-2.2 5.9-5.8 5.7z" /><path d="M8 21h8" /></>,
  leaf: <><path d="M5 19.5C5 10.5 11 4.5 20 4.5c0 9-6 15-13.5 15z" /><path d="M5 19.5C8.5 15 12 11.5 16 8.5" /></>,
  flask: <><path d="M9.5 3.5h5M10.5 3.5v5L5 18a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18L13.5 8.5v-5" /><path d="M7.5 14.5h9" /></>,
  garlic: <><path d="M12 6.5c-1-1.5-.5-3 .5-3.5.8.7 1 1.8.5 3.2" /><path d="M12 6.5c-4 0-6.5 3.6-6.5 7.5 0 4.2 2.9 6.5 6.5 6.5s6.5-2.3 6.5-6.5c0-3.9-2.5-7.5-6.5-7.5z" /><path d="M12 8.5c-1 3-1 8.5 0 11.5M9 8c-1.8 2.5-2.3 7-1 10.5M15 8c1.8 2.5 2.3 7 1 10.5" /></>,
  corn: <><path d="M9 13.5C9 7 10.3 3 12 3s3 4 3 10.5c0 4-1.3 7-3 7s-3-3-3-7z" /><path d="M9.5 9.5h5M9.3 13h5.4M10 16.5h4" /><path d="M12 3v17" /><path d="M8.5 17c-2.5-.5-4-2.5-4.5-5 2.5.5 4 2.5 4.5 5zM15.5 17c2.5-.5 4-2.5 4.5-5-2.5.5-4 2.5-4.5 5z" /></>,
  beans: <><path d="M8.5 4.5a4.5 4.5 0 0 1 4 6.5 4.5 4.5 0 0 1-6.5-4A4.5 4.5 0 0 1 8.5 4.5z" transform="rotate(-15 8 8)" /><path d="M15.5 12.5a4.5 4.5 0 0 1 4 6.5 4.5 4.5 0 0 1-6.5-4 4.5 4.5 0 0 1 2.5-2.5z" transform="rotate(-15 16 16)" /></>,
  chili: <><path d="M14 6.5c0 7-3.5 12-9.5 13.5C7 21.5 18 21 18 8.5" /><path d="M14 6.5c0-1.4 1.3-2.5 4-2.5-.3 2.6-1.6 4-4 4z" /><path d="M14 6.5c-1-.8-1-2-.3-3" /></>,
  onion: <><path d="M12 7.5c-3.8 0-6.5 2.8-6.5 6.5S8.2 20 12 20s6.5-2.3 6.5-6-2.7-6.5-6.5-6.5z" /><path d="M12 7.5c-1.2 3.5-1.2 9 0 12.5M9 8.2c-1.5 3-1.8 7.5-.8 10.8M15 8.2c1.5 3 1.8 7.5.8 10.8" /><path d="M10.5 7.5L9.5 3.5M12 7.3V3M13.5 7.5l1-4" /></>,
  carrot: <><path d="M15 9L4.5 19.5 7 21 17 12" /><path d="M15 9c-1.7-1.7-1.7-4 0-5.5C16.5 5 19 5 20.5 3.5 22 6.5 19.5 9 17 9" transform="translate(-1.5 1.5) scale(.95)" /><path d="M9 15l2 2M12 12l2 2" /></>,
  tomato: <><path d="M12 7c-4.5 0-7.5 2.8-7.5 6.5 0 4 3.3 7 7.5 7s7.5-3 7.5-7C19.5 9.8 16.5 7 12 7z" /><path d="M12 7c-.5-1.5-.3-3 .8-4M12 7l-3-1.5M12 7l3.2-1.2M12 7l-.8 2.5" /></>,
  pepper: <><path d="M9 7.5C6 8.5 4.5 11 4.5 14c0 4 3 6.5 7.5 6.5s7.5-2.5 7.5-6.5c0-3-1.5-5.5-4.5-6.5" /><path d="M9 7.5c1 2.5 5 2.5 6 0M9 7.5c.5-1.5 1.5-2.3 3-2.3s2.5.8 3 2.3" /><path d="M12 5.2V3" /></>,

  // ── Puntos de estado (mantienen su color propio) ──
  dotGreen: <circle cx="12" cy="12" r="6" fill="#84C001" stroke="none" />,
  dotYellow: <circle cx="12" cy="12" r="6" fill="#E4B23F" stroke="none" />,
  dotRed: <circle cx="12" cy="12" r="6" fill="#E36464" stroke="none" />,
  dotBrown: <circle cx="12" cy="12" r="6" fill="#9A7B4F" stroke="none" />,
};

/* Emoji (dato guardado) → nombre de icono. */
const EMOJI_MAP = {
  "📊": "dashboard", "🗂": "receipts", "📈": "chartUp", "📉": "chartDown",
  "💵": "cash", "📦": "box", "🧰": "toolbox", "✅": "checkCircle",
  "👷": "hardhat", "🌿": "leaf", "🧪": "flask", "🌾": "wheat", "⚠": "bellAlert",
  "👔": "crown", "💰": "moneyBag", "🛒": "cart", "🏦": "bank", "🏛": "bank",
  "📅": "calendar", "🗓": "calendarAlt", "✏": "pencilSquare", "📋": "clipboard",
  "🧾": "receipts", "👥": "users", "🗺": "map", "📰": "news", "💾": "save",
  "🔐": "lock", "🔒": "lock", "☁": "cloudUp", "🎯": "target", "🚨": "bellAlert",
  "ℹ": "info", "🤖": "bot", "💧": "droplet", "🗑": "trash", "📍": "pinPoint",
  "🚜": "tractor", "💡": "bulb", "🧴": "spray", "🚛": "truck", "🚚": "truck",
  "📝": "editNote", "🏷": "tag", "📵": "phoneOff", "📷": "camera", "📸": "camera",
  "⛽": "fuel", "⚡": "bolt", "🧬": "dna", "🖨": "printer", "🧑": "user", "👤": "user",
  "❌": "xCircle", "📥": "trayDown", "💬": "chat", "🔄": "refresh", "🔁": "refresh",
  "🔧": "wrench", "🔬": "microscope", "✨": "sparkles", "⏳": "hourglass",
  "🏭": "factory", "🔗": "linkIcon", "🏚": "barn", "🔍": "search", "⭐": "star",
  "💼": "briefcase", "⚖": "scale", "📲": "installMobile", "🏡": "home",
  "🛰": "satellite", "⚙": "cog", "⛑": "helmetCross", "⬇": "arrowDown", "⬆": "arrowUp",
  "📒": "book", "📖": "book", "📤": "trayUp", "➕": "plus", "📑": "docLines",
  "🏁": "flag", "💸": "moneyFly", "👁": "eye", "⏱": "timer", "⏰": "alarm",
  "🏢": "building", "🎁": "gift", "↩": "undo", "📬": "mail", "🚌": "bus",
  "♻": "recycle", "🏪": "store", "🏗": "crane", "▶": "play", "📄": "doc",
  "📐": "ruler", "🧭": "compass", "🌦": "sunCloud", "👍": "thumbUp", "☑": "checkbox",
  "🔀": "shuffle", "🧮": "calculator", "🏆": "trophy", "📱": "smartphone",
  "🌱": "sprout", "🧄": "garlic", "🌽": "corn", "🫘": "beans", "🌶": "chili",
  "🧅": "onion", "🥕": "carrot", "🍅": "tomato", "🫑": "pepper", "➰": "loop",
  "🚁": "drone", "🧑‍🌾": "farmer", "👨‍🌾": "farmer", "👩‍🌾": "farmer",
  "🟢": "dotGreen", "🟡": "dotYellow", "🔴": "dotRed", "🟫": "dotBrown",
};

/* Quita selectores de variación y tonos de piel para encontrar la llave. */
function claveEmoji(s) {
  return s.trim().replace(/[\uFE0E\uFE0F]|[\u{1F3FB}-\u{1F3FF}]/gu, "");
}

export function Ic({ e, name, style, className }) {
  let n = name;
  if (!n) {
    if (e == null) return null;
    if (typeof e !== "string") return e; // p. ej. una <img> de parcela
    n = EMOJI_MAP[claveEmoji(e)];
  }
  const cuerpo = ICONS[n] || ICONS.tag; // sin equivalente: etiqueta genérica
  return (
    <svg className={"ic" + (className ? " " + className : "")} viewBox="0 0 24 24"
      width="1em" height="1em" fill="none" stroke="currentColor" strokeWidth="1.9"
      strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden="true">
      {cuerpo}
    </svg>
  );
}

/* ── Tema claro / oscuro ─────────────────────────────────── */
const oyentesTema = new Set();

/* Saludo según la hora del día y fecha larga en español. */
export function saludoHora() {
  const h = new Date().getHours();
  return h < 12 ? "Buenos días" : h < 19 ? "Buenas tardes" : "Buenas noches";
}
export function fechaLarga() {
  const s = new Date().toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function temaActual() {
  try { return localStorage.getItem("agro_tema") || "oscuro"; } catch { return "oscuro"; }
}
export function aplicarTema(t) {
  document.documentElement.setAttribute("data-tema", t);
  try { localStorage.setItem("agro_tema", t); } catch { /* sin storage */ }
  oyentesTema.forEach(f => f(t));
}
export function aplicarTemaGuardado() {
  document.documentElement.setAttribute("data-tema", temaActual());
}

/* Botón redondo que alterna el tema. Ponlo donde estorbe menos. */
export function ThemeBtn({ style }) {
  const [t, setT] = useState(temaActual());
  useEffect(() => { oyentesTema.add(setT); return () => oyentesTema.delete(setT); }, []);
  const claro = t === "claro";
  return (
    <button type="button" className="theme-btn" style={style} aria-label={claro ? "Cambiar a modo oscuro" : "Cambiar a modo claro"}
      onClick={() => aplicarTema(claro ? "oscuro" : "claro")}>
      <Ic name={claro ? "moon" : "sun"} />
    </button>
  );
}
