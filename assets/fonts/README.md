# fonts/

プロジェクトで使用するフォントファイルとライセンスを格納するディレクトリ。

## ファイル一覧

| ファイル | 状態 | 用途 |
|---|---|---|
| `DSEG14Classic-Regular.ttf` | 同梱済み | pink_bronson.py のセグメント表示 |
| `DSEG7Classic-Regular.ttf` | **要ダウンロード** | pink_bronson.py のセグメント表示 (フォールバックあり) |
| `VT323-Regular.ttf` | **要ダウンロード** | UI全般（ボタン・ラベル・ASCII）|
| `PixelMplus12-Regular.ttf` | **要ダウンロード** | 日本語コンテンツ表示エリア（ログ・STT出力）|
| `DotGothic16-Regular.ttf` | **要ダウンロード** | OBS コントロールパネル / UI 補助 |
| `OFL-DSEG.txt` | 同梱済み | DSEG フォントライセンス (SIL OFL 1.1) |
| `OFL-VT323.txt` | 同梱済み | VT323 ライセンス (SIL OFL 1.1) |
| `OFL-DotGothic16.txt` | 同梱済み | DotGothic16 ライセンス (SIL OFL 1.1) |
| `PixelMplus-LICENSE.txt` | 同梱済み | Pixel Mplus ライセンス (m+ FONT LICENSE) |

## フォントスタック（役割分担）

```
VT323           → ASCII / 英数字 / UI クロム
DotGothic16     → 日本語（ピクセル調 / OBS コントロール）
Pixel Mplus 12  → 日本語コンテンツ（ログ・チャット・STT）
Meiryo          → 上記で対応できない文字のフォールバック
MS Gothic       → 最終フォールバック（OBS / システム）
```

## 不足フォントのダウンロード

### VT323-Regular.ttf
```
https://github.com/phoikoi/VT323/raw/master/VT323-Regular.ttf
```
または: https://fonts.google.com/specimen/VT323

### PixelMplus12-Regular.ttf
```
https://github.com/itouhiro/PixelMplus/raw/master/fonts/PixelMplus12-Regular.ttf
```
または GitHub Releases: https://github.com/itouhiro/PixelMplus/releases

### DotGothic16-Regular.ttf
```
https://github.com/googlefonts/dotgothic16/raw/main/fonts/ttf/DotGothic16-Regular.ttf
```

### DSEG7Classic-Regular.ttf
```
https://github.com/keshikan/DSEG/releases
```

## ライセンス概要

| フォント | 作者 | ライセンス | 商用利用 |
|---|---|---|---|
| DSEG14 Classic / DSEG7 Classic | Keshikan | SIL OFL 1.1 | ✅ |
| VT323 | Peter Hull | SIL OFL 1.1 | ✅ |
| DotGothic16 | Fontworks | SIL OFL 1.1 | ✅ |
| Pixel Mplus | itouhiro | m+ FONT LICENSE | ✅ |

システムフォント (Meiryo, MS Gothic, Consolas 等) は Windows OS 付属のため別途ライセンス不要。
