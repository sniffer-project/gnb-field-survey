# HORIZON KRONOS T78 — Receiver Reference

> Compiled from Horizon's official product page on 2026-06-03.
> Source: https://horizonsis.com/product/horizon-kronos-t78/
>
> **Note on completeness:** Horizon does not publish a downloadable T78 user
> manual or datasheet PDF. Their websites (horizonsis.com / horizon.sg) are
> storefronts with no document portal. The specs below are everything stated on
> the official product page. Figures **not** published there (positioning
> accuracy, battery capacity/runtime, weight, dimensions, drop rating) are
> marked accordingly — request the official datasheet from Horizon (see bottom).

## Your setup
- **Receiver:** Horizon Kronos T78 (GNSS RTK rover/base)
- **Field software:** Map Pro — *confirmed on the official page as the Kronos field app*
- **Controller:** α-GEO S50III (Android 11 handheld; datasheet in `../aGeo-S50III-manual/`)
  - Note: Horizon normally bundles the T78 with the **S60 Pro** controller, but
    Map Pro runs on the S50III the same way — it pairs to the receiver over Bluetooth.

## GNSS engine
- **Channels:** 1408
- **Constellations & signals:**
  - GPS: L1 C/A, L2C, L2P, L5
  - GLONASS: L1 C/A, L1P, L2 C/A, L2P
  - Galileo: E1, E5a, E5b
  - BeiDou: B1, B2, B3, B1C, B2a, B2b
  - QZSS: L1, L2C, L5
  - SBAS: WAAS, EGNOS, MSAS, GAGAN, SDCM
  - IRNSS: L5
- **Positioning accuracy:** *not published on product page — request datasheet*

## IMU / tilt compensation
- IMU tilt measurement up to **60°**
- Measure and stake out points **without leveling the pole**
- **Calibration-free** IMU

## Internal UHF radio
- Frequency range: **410–470 MHz**
- Range: **up to 15 km**
- Multi-protocol internal radio
- Protocols: **Trimtalk 450s, Trimtalk III, Horizon15, Satel**
- Manual frequency input supported

## Communications
- **4G** network support
- **Bluetooth 5** (BLE)
- **Web User Interface** (browser-based receiver configuration — connect to the
  receiver's WiFi/hotspot and open its web UI to set base/rover, radio, NTRIP, etc.)

## Working / correction modes (via Map Pro)
- RTK, Static, PPK, N-RTK (network RTK), UHF-RTK

## Data export formats (Map Pro)
- SHP, DXF, GPX, KML

## Not published on the product page (request from Horizon)
- RTK horizontal / vertical accuracy, static accuracy
- Battery capacity (mAh) and working time
- Weight and dimensions
- IP / drop / shock ratings
- Initialization time, data update rate

---

## Where to get the full operation manual

Horizon publishes no manual PDFs publicly. Closest **brand-matched** operation
guides for the Kronos line (same OEM platform & web UI as the T78 — base/rover
setup, web UI, LED/keys, radio config) are on Scribd (account/subscription
needed to download):

- Kronos C3 GNSS Receiver — User Guide: https://www.scribd.com/document/696285989/Kronos-C3-GNSS-Receiver-User-Guide
- Kronos X1 GNSS Receiver — User Manual: https://www.scribd.com/document/767798037/X1-GNSS-Receiver-User-Manual-2
- GNSS Receiver System — User Guide: https://www.scribd.com/document/959188041/GNSS-Receiver-System-User-Guide

**Official source (recommended) — request the T78 manual + datasheet directly:**
- Horizon Singapore — email: info@horizon.sg · phone: +65 6288 4622
- Product page: https://horizonsis.com/product/horizon-kronos-t78/
