<div align="center">
  <img src="app/launcher-icons/res/drawable-nodpi/launcher_xingchuan_green_01_artwork.png" alt="星川綠~" width="160">
  <h1>Novelia</h1>
  <p>
    面向 <a href="https://n.novelia.cc/">輕小說機翻機器人</a> 的原生 Android 用戶端<br>
    線上閱讀 · 本地書庫 · 雙語對照 · 多裝置同步
  </p>
  <p>
    <a href="#下載與回饋"><img src="https://img.shields.io/badge/Android-8.0%2B-006C4C?style=flat-square&amp;logo=android&amp;logoColor=white" alt="Android 8.0 以上"></a>
    <img src="https://img.shields.io/badge/Kotlin-7F52FF?style=flat-square&amp;logo=kotlin&amp;logoColor=white" alt="Kotlin">
    <img src="https://img.shields.io/badge/Jetpack_Compose-4285F4?style=flat-square&amp;logo=jetpackcompose&amp;logoColor=white" alt="Jetpack Compose">
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0--only-365B48?style=flat-square" alt="GPL-3.0-only"></a>
  </p>
  <p>
    <a href="#維護版本">維護版本</a> ·
    <a href="#介面截圖">介面截圖</a> ·
    <a href="#功能一覽">功能一覽</a> ·
    <a href="#使用">開始使用</a> ·
    <a href="docs/maintenance/troubleshooting.md">疑難排解</a> ·
    <a href="docs/README.md">專案文件</a>
  </p>
  <a href="https://github.com/Capricornus007/novelia/releases">
    <img src="docs/assets/download-apk.svg" alt="前往維護版本的 GitHub Releases" width="240" height="64">
  </a>
</div>

## 維護版本

本儲存庫是 **Capricornus007 維護的 Novelia 復刻（fork）版本**，源自上游 [nobYoQ/novelia](https://github.com/nobYoQ/novelia)，不是原始專案倉庫。此分支的原始碼、Issue 與預覽建置以 [Capricornus007/novelia](https://github.com/Capricornus007/novelia) 為準；這不是 Novelia 服務本身的官方網站，也不代表原站營運方。

此版本保留原有閱讀、書庫、WebDAV、ECH 與預覽建置設計，並完善介面的 **zh-CN（簡體中文）／zh-TW（繁體中文）** 切換。設定位於「我的 → 設定 → 外觀與操作 → 應用程式介面語言」，可選擇跟隨系統、簡體中文或繁體中文。選擇會持久化儲存，重新啟動後仍有效；也會納入一般設定備份及既有 WebDAV 可攜設定。正文另有獨立的「繁體顯示」選項，與介面語言互不取代。

介面沿用硬編碼簡體來源，在顯示層依設定轉換為台灣正體用語；`zh-CN` 保留原始簡體，不會把網站書名、作者或使用者產生的內容當成翻譯資源。這是介面文字轉換，不會變更 Android 系統語言，也不會改寫伺服器內容。

## 螢幕截圖
<table align="center">
  <tr>
    <td align="center"><img src="docs/assets/screenshots/discover-dark.png" alt="深色模式下的探索頁，展示書源、搜尋、篩選和作品列表" width="280"></td>
    <td align="center"><img src="docs/assets/screenshots/webdav-light.png" alt="淺色模式下的 WebDAV 同步頁，展示各類閱讀資料的獨立同步開關" width="280"></td>
  </tr>
  <tr>
    <td align="center">多書源搜尋 · 標籤篩選 · 排行榜</td>
    <td align="center">自選同步範圍 · 連接自己的雲端硬碟</td>
  </tr>
</table>

<p align="center"><sub>應用程式介面截圖；同步頁面使用範例設定，介面可能隨版本更新。</sub></p>

## 功能一覽

| 功能 | 你可以做什麼 |
| :--- | :--- |
| 📚 **整理書架** | 管理本機與雲端收藏，按收藏夾分類、置頂、批次整理，檢視閱讀歷史和更新。 |
| 🔎 **探索作品** | 瀏覽網路書源與文庫，使用標籤、字數篩選和進階搜尋，儲存常用搜尋，接收書源連結分享。 |
| 📖 **自在閱讀** | 在中文、日文與雙語對照間切換，選擇已有的 Sakura / GPT / 有道譯文，支援譯文回退、簡繁顯示和插圖。 |
| 🎨 **依喜好調整** | 自訂字級、行距與紙張主題，切換深色、電子紙、捲動或分頁模式，為單本書儲存閱讀偏好。 |
| 🎧 **隨讀隨記** | 使用系統朗讀、書籤、摘錄和筆記，快取章節後繼續閱讀。 |
| 📂 **讀取本機檔案** | 匯入 EPUB / TXT / SRT，透過檔案管理員的「開啟方式」或單個、批次檔案分享匯入，管理文庫分卷，下載符合條件的已有譯文，使用檔案與文字工具。 |
| 💬 **參與社群** | 瀏覽論壇，閱讀貼文和樓中樓，收藏文章、儲存草稿，依帳號權限發布與編輯。 |
| ☁️ **同步與備份** | 透過 WebDAV 按需同步網路書籍的收藏、進度、書籤和筆記等資料；透過閱讀資料備份遷移本機書庫。 |

## 下載與回饋

**支援 Android 8.0（API 26）以上。** 維護版本的 APK 與發行說明以 [Capricornus007/novelia 的 Releases](https://github.com/Capricornus007/novelia/releases) 實際內容為準；沒有可用的發行版時，可以[從原始碼建置](#建置)。上游發行版請見 [上游 Releases](https://github.com/nobYoQ/novelia/releases)，不代表本維護版本的發布狀態。

- **版本與更新**：已發布版本以 Releases 為準，目前原始碼版本見 [version.properties](version.properties)。
- **預覽版**：Preview APK 工作流可在分支推送後建置 ARM64 Release 預覽包；預設分支成功建置後可更新 `preview` Pre-release。使用前須完成預覽簽名 Secret 設定，未設定或指紋不符時不會產生替代簽名包。下載、簽名與發布前提見 [預覽建置說明](docs/development/getting-started.md#github-actions-自動預覽包)。
- **安裝與升級**：正式包與本地測試包的簽名可能不同；更換安裝來源前，請先完成[閱讀資料備份](docs/data/backup-and-recovery.md)。
- **問題與建議**：在[維護版本的 Issues](https://github.com/Capricornus007/novelia/issues) 回報此版本的用戶端問題；原站內容、帳號和權限問題請聯絡原站。

## 使用

安裝後，可以先以訪客身份瀏覽作品、閱讀可存取的已有章節、匯入本機檔案和檢視社群。

1. **探索一本書**：在「探索」中瀏覽、篩選或搜尋，也可以貼上受支援的書源連結。
2. **放進書架**：收藏喜歡的作品，或在「書架」匯入 EPUB、TXT、SRT 檔案；也可以在檔案管理員中選擇「開啟方式 → Novelia」或「分享 → Novelia」。
3. **調整閱讀體驗**：開啟正文，設定語言、譯文、字級和主題；需要時新增書籤、記筆記或開啟朗讀。
4. **接著讀下去**：在「我的 → 設定」設定 WebDAV 同步，或匯出閱讀資料備份。

### 介面語言與保存

前往「我的 → 設定 → 外觀與操作 → 應用程式介面語言」，選擇「跟隨系統」、「簡體中文（zh-CN）」或「繁體中文」。選擇會持久保存，重新啟動應用程式後仍有效；一般設定備份也會保存此偏好。系統中文地區為台灣、香港或澳門時，「跟隨系統」使用繁體，其他系統語言維持簡體來源。

此功能在顯示層轉換應用程式文字、通知與無障礙說明，不會改變 Android 系統語言，也不會改寫網站內容、使用者輸入、書名或專有名詞。閱讀正文的簡繁顯示仍是另一項獨立設定。

原站和鏡像共用原生登入頁面，支援註冊、找回密碼和快速切換書源；原站驗證請求遵循應用程式的 ECH 設定。獨立論壇使用單獨儲存的登入工作階段，操作權限最終由伺服器驗證。詳見[帳號與登入](docs/network/authentication.md)。

## 建置

使用 Android Studio 開啟儲存庫根目錄。準備 **JDK 17、Android SDK Platform 37、NDK 30.0.16248370、Go 1.27.3**；Go 和 NDK 用於建置應用程式依賴的 ECH 原生函式庫，固定版本見[工具鏈設定](gradle/ech-native.properties)。其他系統需預裝對應版本，或設定 `NOVELIA_GO_HOME`。SDK Build Tools 由 AGP 選擇，專案沒有明確固定其版本。

### 跨平台建置腳本

準備上述 JDK、Android SDK、指定版本 Go 和 NDK，確認 `JAVA_HOME`、`ANDROID_HOME`（或 `local.properties` 的 `sdk.dir`）可用後，在儲存庫根目錄使用建置腳本：

```sh
# 建置 Debug APK
./scripts/build-debug.sh

# 建置本機 Release APK，同時執行單元測試和 Lint
./scripts/build-release.sh --verify
```

腳本也會呼叫 Gradle Wrapper 從 `native/ech` 建置 ECH AAR，即使執行時停用 ECH 也不會略過 Go 原生建置。Go 必須是上述固定版本，可預先放入 PATH，或將 `NOVELIA_GO_HOME` 指向其安裝根目錄；NDK 必須位於 Android SDK 的 `ndk/30.0.16248370`。首次建置需要網路下載 Gradle/Maven 與 Go 模組依賴。

只要建置 Debug APK 而不執行 JVM 測試和完整 Lint，可執行：

```sh
./build.sh :app:assembleDebug
```


本地 Release 使用測試憑證簽名，保留 R8 壓縮與資源精簡。正式發行請遵循[發布指南](docs/maintenance/releasing.md)。

<details>
<summary><strong>建置參數與輸出位置</strong></summary>

- 預設產生通用 APK；`--abi arm64-v8a` 可限定裝置架構。
- 已有完整依賴快取時可加 `--offline`；首次建置需要連接 Google Maven、Maven Central 和 Gradle 發布服務。
- `--verify` 執行對應變體的 JVM 單元測試和 Lint，不執行裝置測試。
- APK 與 SHA-256 校驗檔位於 `outputs/packages/debug/` 或 `outputs/packages/release-local/`，日誌位於 `outputs/logs/`；本機 Release 同時保留 R8 對應表。重複建置會覆蓋相同版本、模式和 ABI 的產物，不會自動安裝或上傳。
- 指令碼自動尋找 JDK / SDK；`./build.sh --check-env` 只檢查環境。完整路徑優先順序、手動設定及快取目錄見[建置指南](docs/development/getting-started.md#自動偵測與手動設定)。

修改版本時，編輯根目錄 [version.properties](version.properties) 中的 `versionName` 並遞增 `versionCode`，再重新封裝。具體操作見[修改版本號並重新編譯](docs/development/getting-started.md#修改版本號並重新編譯)。

</details>


## 驗證

建置時加 `-Verify` 可執行單元測試與 Lint。[Preview APK](.github/workflows/preview-apk.yml) 自動建置 Release 預覽包及其依賴的 Go 單元測試。JVM 單元測試、完整 Lint、裝置測試、唯讀站點聯調和發行前檢查仍按[測試與驗收](docs/quality/testing.md) 手動執行；外部網站測試預設略過，正式發布仍手動執行。

## 工程結構

| 入口 | 閱讀內容 |
| :--- | :--- |
| [文件總目錄](docs/README.md) | 按開發、架構、功能、資料、網路、品質和維護分類查閱 |
| [原始碼目錄導覽](docs/architecture/source-layout.md) | 按介面、資料職責和測試類型定位程式碼 |
| [閱讀器](docs/features/reader.md) | 雙語、排版、分頁、定位、插圖與朗讀 |
| [社群與內容編輯](docs/features/community.md) | 貼文、評論、Markdown、草稿及獨立論壇調適 |
| [資料儲存](docs/data/data-and-storage.md) | 本機檔案、狀態持久化和復原邊界 |
| [安全與隱私](docs/quality/security-and-privacy.md) | 工作階段加密、備份範圍和網路資料處理 |

## 參與貢獻

歡迎回報問題、完善文件或提交程式碼。開始前請閱讀[貢獻指南](.github/CONTRIBUTING.md) 與[行為準則](.github/CODE_OF_CONDUCT.md)；安全問題依[安全政策](.github/SECURITY.md) 回報。

## 授權與範圍

本倉庫沿用上游程式碼與文件的 [GPL-3.0-only](LICENSE) 授權；原作者及其他貢獻者的權利不因復刻而改變。第三方依賴、角色素材及網站上的小說、封面、譯文和使用者內容保留各自權利，不屬於本專案的內容再授權範圍，詳見[來源與素材聲明](NOTICE.md) 與[授權來源](licenses/README.md)。完整開源授權也可在應用程式的「我的 → 說明與關於 → 開源授權」離線檢視。

感謝[輕小說機翻機器人](https://n.novelia.cc/) 與開源社群提供的基礎。願你總能找到下一本想讀的書。
