# U3LogicAnalyzer-WEU6

[中文](#中文说明) | [English](#english)

---

## 中文说明

### 1. 项目简介与硬件来源

**U3LogicAnalyzer-WEU6** 是基于开源 **Q2H2 CH32H417 v2.0** 逻辑分析仪固件，针对 **CH32H417WEU6（QFN68 封装）** 硬件平台移植并完成并发稳定性加固的嵌入式固件仓库。

- **源头上游硬件工程（CH32H417QEU6 原版）**：[立创开源硬件平台 - q2h2/project_bszkxrnf](https://oshwhub.com/q2h2/project_bszkxrnf)
- **本固件适配硬件工程（CH32H417WEU6 硬件版）**：[立创开源硬件平台 - xljxlj/project_zlwgwauv](https://oshwhub.com/xljxlj/project_zlwgwauv)

相比早期 `1v0` 硬件参考工程与上游基线，本仓库完成了以下核心工作：
- **完整外设与时钟门控适配**：修正了调试串口（`PD1` / `GPIOD`）与示波器模拟前端（`PC2`、`PC3` / `GPIOC`）的时钟使能遗漏，确保串口调试与双通道示波器均真实可用。
- **v2.0 完整采样率与协议支持**：完整支持 **25 档采样率**（`6.25 MHz` ~ `200 MHz`）及 8/10-bit HSADC 采样模式，兼容上位机 `U3LogicAnalyzer`（PulseView 分支）。
- **并发安全性与防死锁加固**：修复了高速采集缓冲清零越界、USB 2.0 命令端点寄存器误读、HSADC 双缓冲交接竞态、采样率切换缓冲溢出以及 200 MHz 溢出打印阻塞死锁等问题。
- **命令行无感构建**：内置 `tools/fix_mrs_paths.py` 脚本，自动将 MounRiver Studio（MRS）生成的绝对路径转换为跨机器相对路径，支持 `mingw32-make` 零警告一键编译。

---

### 2. 硬件引脚与外设映射（CH32H417WEU6 / QFN68）

#### 2.1 系统外设对照表

| 功能模块 | 上游基线（QEU6） | 本板硬件（WEU6） | 寄存器 / 宏配置 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| **主控芯片** | CH32H417QEU6 (QFN88) | **CH32H417WEU6 (QFN68)** | RISC-V V3F + V5F 双核 | 400 MHz 系统主频 |
| **逻辑电平阈值 DAC** | `PA4` (`DAC_Channel_1`) | **`PA5` (`DAC_Channel_2`)** | `DAC_SetChannel2Data` | 对应 `VIOH_SET`，支持可调比较阈值 |
| **双通道示波器 HSADC** | `PF0` / `PF1` | **`PC2` / `PC3`** | `HSADC_Channel_2/3` (`GPIOC`) | 同步开启 `RCC_HB2Periph_GPIOC` 时钟 |
| **状态指示灯 LED** | `PB3` / `PB4` | **`PB0` / `PB1`** | `USB_RUN` (`PB0`) / `USB_LINK` (`PB1`) | 推挽输出指示运行与传输状态 |
| **APP 调试串口** | `UART1` (`PA9`) | **`UART6` (`PD1`, AF8)** | `DEBUG_UART6` (`GPIOD`, `921600 bps`) | 同步开启 `RCC_HB2Periph_GPIOD` 时钟 |
| **UHSIF 采样时钟** | `PC0` | **`PC0` (Pin 15)** | `DEF_UHSIF_CLKREMAP1` | 内部时钟源，无需外部飞线 |
| **UHSIF 16 路数据总线** | `PORT16` ~ `PORT31` | **`PORT16` ~ `PORT31`** | **`DEF_UHSIF_PINREMAP2`** | 与上游保持一致，符合手册表 9-33 (`1x`) |

#### 2.2 16 通道逻辑分析仪引脚定义（`D0` ~ `D15`）

在 `DEF_UHSIF_PINREMAP2`（`AFIO_PCFR1[9:8] = 0b10`）配置下，UHSIF 16 位并行从机端口与芯片封装引脚严格一一对应：

| 通道 | MCU 引脚 | QFN68 脚号 | 通道 | MCU 引脚 | QFN68 脚号 |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **D0** | `PD10` | 33 | **D8** | `PF2` | 41 |
| **D1** | `PD11` | 34 | **D9** | `PC6` | 42 |
| **D2** | `PD12` | 35 | **D10** | `PC7` | 43 |
| **D3** | `PD13` | 36 | **D11** | `PC8` | 44 |
| **D4** | `PD14` | 37 | **D12** | `PC9` | 45 |
| **D5** | `PD15` | 38 | **D13** | `PA13` | 46 |
| **D6** | `PF0` | 39 | **D14** | `PA14` | 47 |
| **D7** | `PF1` | 40 | **D15** | `PA15` | 48 |

> **关于 `DEF_UHSIF_PINREMAP2` 的验证说明**：经反汇编 `UHSIF_GPIO_Init()` 确认，库函数将重映射参数左移 8 位直写 `AFIO_PCFR1[9:8]`（无内部查找表）。选用 `DEF_UHSIF_PINREMAP2` 不仅在实机 16 通道注入测试中波形与位序完全准确，而且严格符合《CH32H417 参考手册》表 9-33 中 `UHSIF_PORT_RM = 1x` 的官方定义。

---

### 3. 核心稳定性与并发修复

相比早期参考工程与原始基线，本仓库合入了以下关键修复：

1. **修复 `usb_uhsif_reclen_buf` 越界清零与可见性缺失**：将长度为 255 的 `uint16_t` 数组声明为 `volatile`，并将 `memset` 清零长度由 `255` 字节修正为 `sizeof(usb_uhsif_reclen_buf)`（`510` 字节），消除高半区残留长度引发的错包风险。
2. **修复 USB 2.0 端点控制寄存器误读**：修正 `CMD_SET_START` 等命令响应中误读 `UEP2_TX_CTRL` 来配置 `UEP1_TX_CTRL` 的问题，确保 USB 2.0 高速模式下命令通道与数据通道互不干扰。
3. **重构 HSADC 双缓冲显式队列**：废弃易在丢帧后失步的奇偶计数推算，改用双槽显式环形队列（`adc_buf_queue[2]` + 独立读写游标与溢出保护），杜绝 DMA 写入与 USB 上传访问同一缓冲区的画面撕裂。
4. **修复 200 MHz 硬件溢出阻塞死锁**：恢复向主机上报 `CMD_LOGIC_OVER` 提示弹窗，并将 `DBG_PRINT("logic_over\n")` 限制为**每次采集会话仅打印一次**，避免 921600 波特率串口阻塞主循环导致无法恢复的死锁。
5. **切换采样率安全启停与断线状态复位**：在 `Set_Logic_Para_Fun()` 修改 PLL 分频前先暂停 `UHSIF` 采集引擎；新增 `LOGIC_Upload_State_Reset()`，在 USB 拔插或速率切换时自动清空环形缓冲与状态标志。

---

### 4. 编译指南

#### 4.1 环境要求
- **IDE**：MounRiver Studio（MRS）v1.9x / v2.x（内置 `riscv-wch-elf-gcc 12.2.0` 与 `mingw32-make`）
- **Python**：Python 3.8+（用于运行路径标准化脚本）

#### 4.2 命令行编译步骤
在仓库根目录执行以下命令即可完成路径标准化与 V3F / V5F 双核全量编译：

```powershell
# 1. 将 obj/ 下的 Makefile 与 .mk 中的绝对路径转换为相对路径
python tools/fix_mrs_paths.py

# 2. 编译 V5F 核心工程（主逻辑分析仪与 USB 3.0 协议栈）
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V5F/obj clean
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V5F/obj -B all

# 3. 编译 V3F 核心工程（辅助协处理器与系统初始化）
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V3F/obj clean
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V3F/obj -B all
```

> **提示**：如果你在 MounRiver Studio 图形界面中修改了工程配置并重新生成了 `obj/` 目录，只需再次运行 `python tools/fix_mrs_paths.py` 即可恢复命令行编译。

---

### 5. 固件烧录与升级说明

CH32H417 采用 **IAP 引导程序 + 双核应用程序（V3F + V5F）** 的 Flash 分区结构：

| Flash 地址区间 | 大小 | 固件模块 | 烧录方式 |
| :--- | :--- | :--- | :--- |
| `0x08000000` ~ `0x08005FFF` | 24 KB | `CH32H417_Logic_Analyzer_IAP` | WCH-LinkE (SWD) 首次烧录 |
| `0x08006000` ~ `0x0801FFFF` | 104 KB | `CH32H417_Logic_Analyzer_APP_V3F` | 包含在合并升级包中 |
| `0x08020000` ~ `0x0803FFFF` | 128 KB | `CH32H417_Logic_Analyzer_APP_V5F` | 包含在合并升级包中 |

#### 5.1 日常通过 USB 上位机升级（推荐）
1. 确保板卡已烧录 IAP 引导程序，并通过 USB 数据线连接电脑。
2. 打开 **U3LogicAnalyzer** 上位机软件，点击菜单栏 **帮助 → 固件升级**。
3. 选择双核合并升级包 `CH32H417_Logic_Analyzer_APP_WEU6_merged_for_IAP.bin`（大小固定为 **`133,016` 字节**，由 `V3F.bin` + `0xFF` 填充 + `V5F.bin` 拼接而成）。
4. 等待进度条走完，设备将自动复位并进入新版固件。

> ⚠️ **注意**：切勿直接通过上位机烧录单独的 `V5F.bin`（约 26 KB），否则该镜像会被写入 `0x08006000`（V3F 地址区）导致无法启动。

---

### 6. 实测性能与已知限制

- **USB 3.0 Gen1 物理带宽边界**：
  - 在 **16 通道 @ 200 MHz** 满速采样下，原始数据流高达 `200 MSa/s × 2 Bytes = 400 MB/s`，已触及 USB 3.0 Gen1（5 Gbps 经 8b/10b 编码）的持续有效吞吐物理上限。
  - 当连续采集超过 1~2 秒且 PC 端 xHCI 驱动出现微秒级调度抖动时，片内 256 KB 环形缓冲写满并触发上位机「采集期间发生硬件溢出」提示属正常物理限制。点击确定并停止采集后可直接重新开始，无死锁现象。
  - **推荐采样配置**：16 通道长时间连续无丢点采集建议使用 **≤ 162.5 MHz**（`325 MB/s`）；如需使用 **200 MHz** 满速采样，请在上位机切换至 **8 通道**模式（`200 MB/s`）。
- **采样时钟引脚**：本板 `PC0`（Pin 15）使用内部时钟源，外部排针未引出 `P_CLK` 网络。

---

## English

### 1. Overview & Hardware References

**U3LogicAnalyzer-WEU6** is an open-source firmware port and stability-hardened distribution for the **CH32H417WEU6 (QFN68)** USB 3.0 Logic Analyzer & Oscilloscope hardware, based on the upstream **Q2H2 CH32H417 v2.0** codebase.

- **Original Upstream Hardware Project (CH32H417QEU6)**: [OSHWHub - q2h2/project_bszkxrnf](https://oshwhub.com/q2h2/project_bszkxrnf)
- **Target Hardware Project Adapted by This Firmware (CH32H417WEU6)**: [OSHWHub - xljxlj/project_zlwgwauv](https://oshwhub.com/xljxlj/project_zlwgwauv)

Key improvements over the legacy `1v0` vendor reference and upstream baseline:
- **Complete Peripheral & Clock-Gating Port**: Fixed missing `RCC_HB2PeriphClockCmd` enables for `GPIOD` (`PD1` / `UART6` debug TX) and `GPIOC` (`PC2`/`PC3` dual-channel HSADC inputs).
- **Full v2.0 Sample-Rate Table**: Supports all **25 sample rates** (`6.25 MHz` to `200 MHz`) and 8/10-bit HSADC modes, fully compatible with the `U3LogicAnalyzer` (PulseView) host software.
- **Concurrency & Deadlock Hardening**: Resolved `memset` buffer-clear truncation, USB 2.0 `UEP1_TX_CTRL` register misread, HSADC dual-buffer race conditions, sample-rate switching overflows, and blocking `DBG_PRINT` deadlocks at 200 MHz.
- **Reproducible CLI Builds**: Includes `tools/fix_mrs_paths.py` to normalize MounRiver Studio absolute paths into portable relative paths for zero-warning `mingw32-make` builds.

---

### 2. Hardware Porting Matrix (CH32H417WEU6 / QFN68)

#### 2.1 Peripheral Mapping

| Peripheral | Upstream (QEU6) | Target Board (WEU6) | Firmware Configuration | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **MCU** | CH32H417QEU6 (QFN88) | **CH32H417WEU6 (QFN68)** | Dual-core RISC-V (V3F + V5F) | 400 MHz system clock |
| **Threshold DAC** | `PA4` (`DAC_Channel_1`) | **`PA5` (`DAC_Channel_2`)** | `DAC_SetChannel2Data` | Programmable logic threshold (`VIOH_SET`) |
| **Dual-Ch HSADC** | `PF0` / `PF1` | **`PC2` / `PC3`** | `HSADC_Channel_2/3` (`GPIOC`) | Enabled `RCC_HB2Periph_GPIOC` clock |
| **Status LEDs** | `PB3` / `PB4` | **`PB0` / `PB1`** | `USB_RUN` (`PB0`) / `USB_LINK` (`PB1`) | Push-pull status indicators |
| **Debug UART** | `UART1` (`PA9`) | **`UART6` (`PD1`, AF8)** | `DEBUG_UART6` (`GPIOD`, `921600 bps`) | Enabled `RCC_HB2Periph_GPIOD` clock |
| **UHSIF Sample Clock** | `PC0` | **`PC0` (Pin 15)** | `DEF_UHSIF_CLKREMAP1` | Internal clock routing |
| **UHSIF 16-Bit Data Bus** | `PORT16` – `PORT31` | **`PORT16` – `PORT31`** | **`DEF_UHSIF_PINREMAP2`** | Kept identical to upstream (`RM = 1x`) |

#### 2.2 16-Channel Logic Analyzer Pinout (`D0` – `D15`)

With `DEF_UHSIF_PINREMAP2` (`AFIO_PCFR1[9:8] = 0b10`), `PORT16`–`PORT31` map directly to the 16 input pins per *CH32H417 Reference Manual* Table 9-33:

| Channel | MCU Pin | QFN68 Pin | Channel | MCU Pin | QFN68 Pin |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **D0** | `PD10` | 33 | **D8** | `PF2` | 41 |
| **D1** | `PD11` | 34 | **D9** | `PC6` | 42 |
| **D2** | `PD12` | 35 | **D10** | `PC7` | 43 |
| **D3** | `PD13` | 36 | **D11** | `PC8` | 44 |
| **D4** | `PD14` | 37 | **D12** | `PC9` | 45 |
| **D5** | `PD15` | 38 | **D13** | `PA13` | 46 |
| **D6** | `PF0` | 39 | **D14** | `PA14` | 47 |
| **D7** | `PF1` | 40 | **D15** | `PA15` | 48 |

---

### 3. Key Stability & Concurrency Fixes

1. **`usb_uhsif_reclen_buf` Visibility & Full Zeroing**: Marked `usb_uhsif_reclen_buf[255]` as `volatile` and fixed `memset` length from `255` bytes to `sizeof(usb_uhsif_reclen_buf)` (`510` bytes), preventing stale packet lengths in indices `128..254`.
2. **USB 2.0 Endpoint Control Register Fix**: Fixed `CMD_SET_START` acknowledgment logic reading `UEP2_TX_CTRL` instead of `UEP1_TX_CTRL` in High-Speed mode.
3. **Explicit HSADC Dual-Buffer Queue**: Replaced parity-based buffer toggling with an explicit 2-slot ring queue (`adc_buf_queue[2]`) with read/write cursors and overflow counters to prevent DMA/USB buffer tearing.
4. **200 MHz Overflow Deadlock Prevention**: Restored `CMD_LOGIC_OVER` host notifications and rate-limited `DBG_PRINT("logic_over\n")` to **once per capture session**, eliminating UART blocking loops at `921600 bps`.
5. **Safe Sample-Rate Switching & Disconnect Reset**: Halts `UHSIF` before reconfiguring PLL dividers in `Set_Logic_Para_Fun()`, and resets ring buffers via `LOGIC_Upload_State_Reset()` upon USB disconnect/re-enumeration.

---

### 4. Building from Source

#### Prerequisites
- **MounRiver Studio (MRS)** toolchain (`riscv-wch-elf-gcc 12.2.0` and `mingw32-make`)
- **Python 3.8+**

#### Build Commands
```powershell
# 1. Normalize absolute paths in MRS-generated build files
python tools/fix_mrs_paths.py

# 2. Build V5F core firmware
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V5F/obj clean
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V5F/obj -B all

# 3. Build V3F core firmware
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V3F/obj clean
mingw32-make -C firmware/CH32H417_Logic_Analyzer_APP/V3F/obj -B all
```

---

### 5. Flashing & Firmware Upgrade

| Flash Address | Size | Image | Method |
| :--- | :--- | :--- | :--- |
| `0x08000000` – `0x08005FFF` | 24 KB | `CH32H417_Logic_Analyzer_IAP` | WCH-LinkE (SWD) initial flash |
| `0x08006000` – `0x0801FFFF` | 104 KB | `CH32H417_Logic_Analyzer_APP_V3F` | Bundled in merged IAP image |
| `0x08020000` – `0x0803FFFF` | 128 KB | `CH32H417_Logic_Analyzer_APP_V5F` | Bundled in merged IAP image |

1. Flash `CH32H417_Logic_Analyzer_IAP` to `0x08000000` via SWD once.
2. Connect the board over USB, open **U3LogicAnalyzer**, and navigate to **Help → Firmware Upgrade**.
3. Select the **`133,016`-byte** merged binary (`CH32H417_Logic_Analyzer_APP_WEU6_merged_for_IAP.bin`). Do **not** flash a standalone `V5F.bin` directly via USB IAP.

---

### 6. Known Limitations

- **USB 3.0 Gen1 Physical Bandwidth Ceiling**:
  - Streaming **16 channels @ 200 MHz** generates `400 MB/s` (`200 MSa/s × 2 Bytes`), saturating the sustained payload ceiling of USB 3.0 Gen1 (`5 Gbps` 8b/10b). Continuous captures longer than ~1–2 seconds may trigger a hardware overflow warning when host xHCI polling jitters exhaust the 256 KB on-chip ring buffer. Stopping and restarting capture recovers immediately without deadlocking.
  - **Recommended settings**: Use **≤ 162.5 MHz** (`325 MB/s`) for long continuous 16-channel captures, or switch to **8-channel mode** (`200 MB/s`) for continuous **200 MHz** captures.
