# U3LogicAnalyzer-WEU6 Firmware

面向 **CH32H417WEU6 (QFN-68)** 的 USB 3.0 逻辑分析仪 / 高速示波器固件工程。
Firmware for a USB 3.0 logic analyzer & high-speed oscilloscope built on **CH32H417WEU6 (QFN-68)**.

[中文](#中文) | [English](#english)

---

## 中文

### 项目简介

本仓库是 **CH32H417WEU6（QFN-68 封装）** 逻辑分析仪的固件工程。固件基线取自
**Q2H2 原版 v2.0**（面向 CH32H417QEU6 / QFN-128），按 WEU6 的引脚与外设资源重新梳理移植，
搭配 `U3LogicAnalyzer`（PulseView 0.5 分支）上位机使用。

- **主控**：CH32H417WEU6，QFN-68（8×8 mm），RISC-V 双核（V3F + V5F）
- **接口**：USB 3.0 SuperSpeed（经 CH9441P Type-C 正反插切换）
- **采样**：16 路数字通道（UHSIF 并行采样）+ 2 路 HSADC 模拟通道
- **软件生态**：130 种协议解码（I²C / SPI / UART 等），上位机基于 sigrok / PulseView

> **`Commit 1` 为 Q2H2 原版 v2.0 的纯净基线，`.c` / `.h` 源码与上游逐字节一致，未做任何修改。**
> 硬件适配将在后续提交中分步落地，见 [移植路线图](#移植路线图)。

### 仓库结构

```
U3LogicAnalyzer-WEU6/
├── firmware/                              # 固件工程（Q2H2 原版 v2.0 基线）
│   ├── CH32H417_Logic_Analyzer_APP/       # 主应用固件
│   │   ├── CH32H417_Logic_Analyzer.wvsln  # MounRiver Studio 解决方案
│   │   ├── Common/                        # 业务代码：logic / uhsif / usb / hardware / Debug / Ld
│   │   ├── V3F/                           # V3F 核工程（.cproject / .wvproj / User / obj）
│   │   └── V5F/                           # V5F 核工程（实际业务运行体）
│   ├── CH32H417_Logic_Analyzer_IAP/       # USB-IAP 引导固件
│   │   ├── CH32H417_IAP.wvsln
│   │   ├── Common/                        # iap / flash / hardware / USB
│   │   ├── V3F/   └── V5F/
│   └── SRC/                               # WCH 官方 SDK（Core / Debug / Ld / Peripheral / Startup）
├── hardware/                              # 硬件资料
│   ├── SCH_Schematic1_1_2026-11-21.pdf     # CH32H417WEU6 QFN-68 原理图
│   └── Netlist_Schematic1_1_2026-11-21.enet# 网表（嘉立创专业版，含逐脚网络）
├── .gitattributes                         # 行尾规范（* text=auto）
└── .gitignore                             # 排除编译产物，保留闭源 UHSIF 库
```

**双核说明**：`Common/Debug/debug.h` 中 `Run_Core = Run_Core_V5F`，因此 **V3F 镜像只负责唤醒 V5F 并进入 STOP，
全部业务（USB、UHSIF 采样、HSADC、LED）运行在 V5F 核**。烧录时使用双核合并镜像
（`V3F@0x000000` + `0xFF` 填充至 `0x01A000` + `V5F@0x01A000`），由 MounRiver Studio 按 `V5F/.kernel`
的 `mergedOptions` 自动生成 `obj/CH32H417_Logic_Analyzer_APP.bin`。

### 硬件移植对照表

下表为 **Q2H2 原版（CH32H417QEU6 / QFN-128）** 与 **CH32H417WEU6（QFN-68）** 的完整引脚对照，
数据来自两版板卡的实测网表（`.enet`），非推导。

| 功能 | Q2H2 原版 QEU6（QFN-128） | CH32H417WEU6（QFN-68） | 是否需改代码 |
|---|---|---|---|
| **调试串口** | `UART1` / `PA9`（AF7，脚 88），接 2P 排针 | `UART6` / `PD1`（AF8，脚 53），板上无排针 | 是 |
| **阈值 DAC**（VIO18 调压） | `DAC1` / `PA4`（脚 39）→ `FB`，串 27 kΩ | `DAC2` / `PA5`（脚 20）→ `VIOH_SET`，串 27 kΩ | 是 |
| **示波器通道 0** | `HSADC4` / `PF8`（脚 19）→ `HSADC0` | `HSADC2` / `PC2`（脚 17）→ `L_ADC0` | 是 |
| **示波器通道 1** | `HSADC5` / `PF9`（脚 20）→ `HSADC1` | `HSADC3` / `PC3`（脚 18）→ `L_ADC1` | 是 |
| **状态 LED 1** | `PB3`（脚 115），串 1 kΩ | `PB0`（脚 21），串 5.1 kΩ | 是 |
| **状态 LED 2** | `PB4`（脚 116），串 1 kΩ | `PB1`（脚 22），串 5.1 kΩ | 是 |
| **UHSIF 重映射** | `DEF_UHSIF_PINREMAP2` | `DEF_UHSIF_PINREMAP0` | 是 |
| **采样时钟抽头** | `PC0`（脚 26）→ 网 `P_CLK`，仅接测试点 TP1 | `PC0`（脚 15）**未连接**（原版本就只作测试点） | 否 |
| **USB 3.0 SS** | `SSTXA/B` `SSRXA/B`（脚 124/123/127/126） | `SSTXA/B` `SSRXA/B`（脚 2/1/5/4），均经 CH9441P | 否 |
| **USB 2.0** | `PB8` / `PB9`（脚 120/121） | `PB8` / `PB9`（脚 67/68） | 否 |

**16 路数字通道：两封装引脚完全一致，无需改动。**

| 通道 | D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|---|---|
| 引脚 | `PD10` | `PD11` | `PD12` | `PD13` | `PD14` | `PD15` | `PF0` | `PF1` |

| 通道 | D8 | D9 | D10 | D11 | D12 | D13 | D14 | D15 |
|---|---|---|---|---|---|---|---|---|
| 引脚 | `PF2` | `PC6` | `PC7` | `PC8` | `PC9` | `PA13` | `PA14` | `PA15` |

**模拟前端差异（硬件侧）**：QEU6 原版为 1 kΩ 串阻 + 7 pF 对地；WEU6 板为 499 Ω 串阻 + TVS 钳位（`H5VU25U`）
+ 100 kΩ 上/下拉，模拟前端置于外部模块，经 36P（1.27 mm）连接器接入。

### 构建

**固件（MounRiver Studio）**

1. 用 MounRiver Studio 打开 `firmware/CH32H417_Logic_Analyzer_APP/CH32H417_Logic_Analyzer.wvsln`；
2. 选择 `V5F` 工程执行 Build（会按 `.kernel` 规则自动生成双核合并镜像）；
3. 首次烧录：WCH-Link 经 SWD 将 IAP 固化到 `0x08000000`（24 KB 区）；
4. 后续升级：用上位机「帮助 → 固件升级」选择合并镜像。

> **注意**：仓库不包含 `obj/` 目录与任何 `.o`（除闭源库 `ch32h417_uhsif_it.o`）、`.d`、`.elf`、`.map`、`.lst`。
> 若改用命令行 `make` 构建，需先让 MounRiver 重新生成 `obj/` 下的 `makefile` 与 `subdir.mk`
> ——发布包内这些文件含原作者本机的绝对路径（`e:\Workspace\...`，GBK 编码），不可直接在本机构建。

**上位机（U3LogicAnalyzer）**

上位机源码与预编译包不纳入本仓库跟踪，需另行获取。上位机基于 CMake 构建，
Windows 平台使用 MSYS2 MINGW64 工具链（`glib2` / `glibmm` / `libusb` / `hidapi` / `libzip` / `boost` / `qt5-static` / `python`）。

### 移植路线图

| 阶段 | 内容 | 状态 |
|---|---|---|
| **Commit 1** | Q2H2 原版 v2.0 纯净基线（`firmware/` + `hardware/`） | ✅ 本提交 |
| Commit 2 | 硬件外设适配：DAC `PA4→PA5` / `DAC1→DAC2`；HSADC `PF8/PF9→PC2/PC3`、`CH4/5→CH2/3`；LED `PB3/PB4→PB0/PB1`；UART `PA9→PD1`（`UART1→UART6`）；UHSIF `PINREMAP2→PINREMAP0`；`hardware.c` ADC 时钟 `GPIOF→GPIOC` | 待办 |
| Commit 3 | 高采样率稳定性优化：HSADC 双缓冲交接队列、USB 重连状态复位、切档时序修正、溢出上报限流 | 待办 |
| Commit 4 | 文档与构建脚本完善：`.gitignore` 校验、双核合并镜像生成脚本、引脚校验清单 | 待办 |

### 已知限制

- `PINREMAP0` 与 `PINREMAP2` 在**同一组 16 引脚**上的位序/极性是否等价，尚待查阅
  `CH32H417RM` 的 UHSIF 复用章节或实机验证。
- UHSIF 底层实现位于闭源预编译库 `Common/ch32h417_uhsif_it.o`，无源码；该文件是链接必需项，
  故在 `.gitignore` 中被显式保留（`!**/Common/ch32h417_uhsif_it.o`）。
- IAP 引导固件不含 UHSIF，因此其中没有 `ch32h417_uhsif_it.o`。

### 致谢与许可

- 固件原始工程：**Q2H2**（OSHWHub「CH32H417 Logic Analyzer」）
- MCU 与外设库：南京沁恒微电子（WCH）CH32H417 SDK
- 上位机：sigrok / PulseView（GPL-3.0）

各文件的版权与许可遵循其原属工程，详见源码文件头注释。

---

## English

### Overview

Firmware for a USB 3.0 logic analyzer / high-speed oscilloscope built on **CH32H417WEU6 (QFN-68)**.
The code base is the **Q2H2 original v2.0** firmware (targeting CH32H417QEU6 / QFN-128),
re-organized and being ported to the WEU6 package. It works with the `U3LogicAnalyzer`
(PulseView 0.5 fork) host software.

- **MCU**: CH32H417WEU6, QFN-68 (8×8 mm), dual RISC-V cores (V3F + V5F)
- **Interface**: USB 3.0 SuperSpeed (via CH9441P Type-C mux)
- **Acquisition**: 16 digital channels (UHSIF parallel) + 2 HSADC analog channels
- **Ecosystem**: 130 protocol decoders (I²C / SPI / UART …), host based on sigrok / PulseView

> **`Commit 1` is a pristine Q2H2 v2.0 baseline — every `.c` / `.h` file is byte-identical to upstream.**
> Hardware adaptation lands in follow-up commits; see [Roadmap](#roadmap).

### Repository layout

```
U3LogicAnalyzer-WEU6/
├── firmware/                              # Firmware (Q2H2 v2.0 baseline)
│   ├── CH32H417_Logic_Analyzer_APP/       # Main application (Common / V3F / V5F + .wvsln)
│   ├── CH32H417_Logic_Analyzer_IAP/       # USB-IAP bootloader (Common / V3F / V5F + .wvsln)
│   └── SRC/                               # WCH SDK (Core / Debug / Ld / Peripheral / Startup)
├── hardware/                              # CH32H417WEU6 QFN-68 schematic + netlist
├── .gitattributes                         # line-ending policy (* text=auto)
└── .gitignore                             # excludes build artifacts, keeps the closed-source UHSIF lib
```

**Dual-core note**: `Run_Core = Run_Core_V5F` in `Common/Debug/debug.h`, so the **V3F image only wakes V5F
and enters STOP; all functionality (USB, UHSIF acquisition, HSADC, LEDs) runs on V5F**. The flashed image is a
dual-core merge (`V3F@0x000000` + `0xFF` padding to `0x01A000` + `V5F@0x01A000`), produced by MounRiver Studio
from `mergedOptions` in `V5F/.kernel`.

### Hardware porting matrix

Source: measured netlists (`.enet`) of both boards — not inferred.

| Function | Q2H2 QEU6 (QFN-128) | CH32H417WEU6 (QFN-68) | Code change |
|---|---|---|---|
| **Debug UART** | `UART1` / `PA9` (AF7, pin 88), 2-pin header | `UART6` / `PD1` (AF8, pin 53), no header | Yes |
| **Threshold DAC** (VIO18 trim) | `DAC1` / `PA4` (pin 39) → `FB`, 27 kΩ series | `DAC2` / `PA5` (pin 20) → `VIOH_SET`, 27 kΩ series | Yes |
| **Scope channel 0** | `HSADC4` / `PF8` (pin 19) → `HSADC0` | `HSADC2` / `PC2` (pin 17) → `L_ADC0` | Yes |
| **Scope channel 1** | `HSADC5` / `PF9` (pin 20) → `HSADC1` | `HSADC3` / `PC3` (pin 18) → `L_ADC1` | Yes |
| **Status LED 1** | `PB3` (pin 115), 1 kΩ | `PB0` (pin 21), 5.1 kΩ | Yes |
| **Status LED 2** | `PB4` (pin 116), 1 kΩ | `PB1` (pin 22), 5.1 kΩ | Yes |
| **UHSIF pin-remap** | `DEF_UHSIF_PINREMAP2` | `DEF_UHSIF_PINREMAP0` | Yes |
| **Sampling clock tap** | `PC0` (pin 26) → `P_CLK`, test point TP1 only | `PC0` (pin 15) unconnected (upstream was TP-only too) | No |
| **USB 3.0 SS** | `SSTXA/B` `SSRXA/B` (pins 124/123/127/126) | `SSTXA/B` `SSRXA/B` (pins 2/1/5/4), both via CH9441P | No |
| **USB 2.0** | `PB8` / `PB9` (pins 120/121) | `PB8` / `PB9` (pins 67/68) | No |

**16 digital channels: identical pins on both packages — no code change.**

| Ch | D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 |
|---|---|---|---|---|---|---|---|---|
| Pin | `PD10` | `PD11` | `PD12` | `PD13` | `PD14` | `PD15` | `PF0` | `PF1` |

| Ch | D8 | D9 | D10 | D11 | D12 | D13 | D14 | D15 |
|---|---|---|---|---|---|---|---|---|
| Pin | `PF2` | `PC6` | `PC7` | `PC8` | `PC9` | `PA13` | `PA14` | `PA15` |

**Analog front-end difference (hardware)**: QEU6 uses 1 kΩ series + 7 pF to ground; the WEU6 board uses
499 Ω series + TVS clamp (`H5VU25U`) + 100 kΩ pull, with the analog front-end on an external module
connected through a 36-pin (1.27 mm) header.

### Build

**Firmware (MounRiver Studio)**

1. Open `firmware/CH32H417_Logic_Analyzer_APP/CH32H417_Logic_Analyzer.wvsln`;
2. Build the `V5F` project (the dual-core merged image is generated from `.kernel` rules);
3. First flash: burn IAP to `0x08000000` (24 KB region) via WCH-Link/SWD;
4. Updates: use the host «Help → Firmware Upgrade» with the merged image.

> **Note**: the repo ships no `obj/`, and no `.o` (except the closed-source `ch32h417_uhsif_it.o`), `.d`,
> `.elf`, `.map`, `.lst`. To build from the command line, let MounRiver regenerate the `obj/` makefiles first —
> the ones in the vendor package embed the author's absolute paths (`e:\Workspace\...`, GBK encoded).

**Host software (U3LogicAnalyzer)**

Not tracked in this repository. Built with CMake; on Windows use the MSYS2 MINGW64 toolchain
(`glib2` / `glibmm` / `libusb` / `hidapi` / `libzip` / `boost` / `qt5-static` / `python`).

### Roadmap

| Stage | Content | Status |
|---|---|---|
| **Commit 1** | Pristine Q2H2 v2.0 baseline (`firmware/` + `hardware/`) | ✅ this commit |
| Commit 2 | Peripheral adaptation: DAC `PA4→PA5` / `DAC1→DAC2`; HSADC `PF8/PF9→PC2/PC3`, `CH4/5→CH2/3`; LED `PB3/PB4→PB0/PB1`; UART `PA9→PD1` (`UART1→UART6`); UHSIF `PINREMAP2→PINREMAP0`; ADC clock `GPIOF→GPIOC` in `hardware.c` | Planned |
| Commit 3 | High-sample-rate stability: HSADC double-buffer hand-off queue, USB reconnect state reset, sample-rate switch sequencing, overflow report throttling | Planned |
| Commit 4 | Docs & build tooling: `.gitignore` validation, merged-image generation script, pin check list | Planned |

### Known limitations

- Whether `PINREMAP0` and `PINREMAP2` map the **same 16 pins** with identical bit order/polarity is still
  unverified — needs the UHSIF multiplexing chapter of `CH32H417RM` or a bench test.
- The UHSIF low-level implementation is a closed-source precompiled object
  (`Common/ch32h417_uhsif_it.o`) with no source available; it is required for linking, hence explicitly
  preserved in `.gitignore` (`!**/Common/ch32h417_uhsif_it.o`).
- The IAP bootloader does not use UHSIF and therefore contains no `ch32h417_uhsif_it.o`.

### Credits & license

- Original firmware: **Q2H2** (OSHWHub "CH32H417 Logic Analyzer")
- MCU & peripheral library: Nanjing Qinheng Microelectronics (WCH) CH32H417 SDK
- Host software: sigrok / PulseView (GPL-3.0)

Copyright and license of each file follow its originating project; see the file header comments.
